from django.conf import settings
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import AccountToken, RoleAssignment, User
from accounts.services import issue_account_token
from core.pagination import BoundedPagination
from core.permissions import IsAdministrator, IsAuthenticatedWithStaffMFA, IsReceptionOrAdmin
from core.services import audit, idempotent, safe_model_projection
from core.throttling import DatabaseScopedRateThrottle

from .models import Chamber, ConsentRecord, Department, DoctorProfile, Hospital, Location, PatientCorrectionHistory, PatientProfile, PrivacyNoticeVersion
from .serializers import (
    AssistedPatientCreateSerializer,
    ChamberAdminSerializer,
    ClaimInvitationSerializer,
    ConsentCreateSerializer,
    ConsentSerializer,
    DepartmentAdminSerializer,
    DepartmentPublicSerializer,
    DoctorAdminSerializer,
    DoctorPublicSerializer,
    DuplicateCheckSerializer,
    HospitalAdminSerializer,
    HospitalPublicSerializer,
    LocationAdminSerializer,
    PatientCorrectionSerializer,
    PatientDeactivateSerializer,
    PatientSerializer,
    PrivacyNoticeCreateSerializer,
)


class HospitalPublicView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        hospital = Hospital.objects.filter(is_active=True).select_related("active_privacy_notice").first()
        if not hospital:
            return Response({"detail": "Hospital configuration is not available.", "code": "not_configured"}, status=503)
        return Response(HospitalPublicSerializer(hospital).data)


class DepartmentPublicView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        queryset = Department.objects.filter(is_active=True, hospital__is_active=True)
        return Response(DepartmentPublicSerializer(queryset, many=True).data)


class DoctorPublicListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "public"

    def get(self, request):
        queryset = (
            DoctorProfile.objects.filter(
                is_active=True,
                user__is_active=True,
                hospital__is_active=True,
                departments__is_active=True,
                departments__hospital__is_active=True,
            )
            .prefetch_related(Prefetch("departments", queryset=Department.objects.filter(is_active=True)))
            .distinct()
        )
        department = request.query_params.get("department")
        if department:
            queryset = queryset.filter(departments__id=department, departments__is_active=True)
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(Q(display_name__icontains=search) | Q(designation__icontains=search))
        return Response(DoctorPublicSerializer(queryset[:100], many=True).data)


class DoctorPublicDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, doctor_id):
        doctor = (
            DoctorProfile.objects.filter(
                pk=doctor_id,
                is_active=True,
                user__is_active=True,
                hospital__is_active=True,
                departments__is_active=True,
            )
            .prefetch_related(Prefetch("departments", queryset=Department.objects.filter(is_active=True)))
            .distinct()
            .first()
        )
        if not doctor:
            return Response({"detail": "Doctor not found.", "code": "not_found"}, status=404)
        return Response(DoctorPublicSerializer(doctor).data)


class NoDeleteAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdministrator]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def get_serializer(self, *args, **kwargs):
        if self.action == "create" and "data" in kwargs and isinstance(kwargs["data"], dict) and "hospital" not in kwargs["data"]:
            data = kwargs["data"].copy()
            hospital = Hospital.objects.filter(is_active=True).first()
            if hospital and self.serializer_class in {DepartmentAdminSerializer, LocationAdminSerializer}:
                data["hospital"] = str(hospital.pk)
            kwargs["data"] = data
        return super().get_serializer(*args, **kwargs)

    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def create(self, request, *args, **kwargs):
        scope = f"configuration.{self.get_serializer_class().__name__}.create"
        return idempotent(
            request,
            scope,
            lambda: viewsets.ModelViewSet.create(self, request, *args, **kwargs),
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_active and request.data.get("is_active") is False:
            return Response(
                {"detail": "Use the reasoned deactivation action.", "code": "reason_required"},
                status=400,
            )
        scope = f"configuration.{self.get_serializer_class().__name__}.{kwargs.get('pk')}.update"
        return idempotent(
            request,
            scope,
            lambda: viewsets.ModelViewSet.update(self, request, *args, **kwargs),
        )

    def perform_create(self, serializer):
        obj = serializer.save()
        audit(self.request, "configuration.created", obj, "create", serializer.validated_data)

    def perform_update(self, serializer):
        before = self.configuration_projection(serializer.instance)
        obj = serializer.save()
        audit(
            self.request,
            "configuration.updated",
            obj,
            "update",
            {"before": before, "after": self.configuration_projection(obj)},
        )

    @staticmethod
    def configuration_projection(obj):
        fields_by_type = {
            Department: ("hospital_id", "name", "description", "display_order", "is_active"),
            Location: ("hospital_id", "name", "code", "address", "phone", "email", "is_active"),
            Chamber: ("location_id", "name", "is_active"),
            DoctorProfile: (
                "hospital_id",
                "user_id",
                "doctor_code",
                "display_name",
                "designation",
                "registration_reference",
                "biography",
                "consultation_fee_minor",
                "is_active",
            ),
        }
        many = ("departments",) if isinstance(obj, DoctorProfile) else ()
        return safe_model_projection(obj, fields_by_type[type(obj)], many)

    def deactivate(self, request, pk=None):
        obj = self.get_object()
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            return Response({"detail": "A concise operational reason is required.", "code": "reason_required"}, status=400)

        def operation():
            locked = obj.__class__.objects.select_for_update().get(pk=obj.pk)
            before = self.configuration_projection(locked)
            from operations.models import Appointment, Schedule

            confirmed = Appointment.objects.filter(status=Appointment.Status.CONFIRMED)
            schedules = Schedule.objects.filter(is_active=True)
            if isinstance(locked, DoctorProfile):
                confirmed = confirmed.filter(doctor=locked)
                schedules = schedules.filter(doctor=locked)
            elif isinstance(locked, Department):
                confirmed = confirmed.filter(department=locked)
                affected_doctors = DoctorProfile.objects.filter(departments=locked).prefetch_related("departments")
                blocking_doctor_ids = [doctor.pk for doctor in affected_doctors if not doctor.departments.filter(is_active=True).exclude(pk=locked.pk).exists()]
                schedules = schedules.filter(doctor_id__in=blocking_doctor_ids)
            elif isinstance(locked, Location):
                confirmed = confirmed.filter(location=locked)
                schedules = schedules.filter(location=locked)
            else:
                confirmed = confirmed.filter(chamber=locked)
                schedules = schedules.filter(chamber=locked)
            dependencies = {
                "confirmed_appointments": confirmed.distinct().count(),
                "active_schedules": schedules.distinct().count(),
            }
            if any(dependencies.values()):
                return {
                    "detail": "Deactivate dependent schedules and reschedule or close confirmed appointments first.",
                    "code": "active_dependencies",
                    "dependencies": dependencies,
                }, 409
            locked.is_active = False
            locked.save(update_fields=["is_active", "updated_at"])
            role_changes = None
            if isinstance(locked, DoctorProfile):
                before_roles = sorted(
                    locked.user.role_assignments.filter(is_active=True).values_list("role", flat=True)
                )
                locked.user.role_assignments.filter(
                    role=RoleAssignment.Role.DOCTOR,
                    is_active=True,
                ).update(is_active=False)
                remaining_roles = set(
                    locked.user.role_assignments.filter(is_active=True).values_list("role", flat=True)
                )
                remaining_staff_roles = remaining_roles & {
                    RoleAssignment.Role.DOCTOR,
                    RoleAssignment.Role.RECEPTIONIST,
                    RoleAssignment.Role.ADMINISTRATOR,
                }
                if not remaining_staff_roles:
                    locked.user.mfa_devices.filter(revoked_at__isnull=True).update(
                        revoked_at=timezone.now()
                    )
                locked.user.is_active = bool(remaining_roles)
                locked.user.save(update_fields=["is_active", "updated_at"])
                role_changes = {
                    "before": before_roles,
                    "after": sorted(remaining_roles),
                    "user_active": locked.user.is_active,
                }
            changes = {
                "before": before,
                "after": self.configuration_projection(locked),
            }
            if role_changes is not None:
                changes["active_roles"] = role_changes
            audit(request, "configuration.deactivated", locked, "deactivate", changes, reason)
            return self.get_serializer(locked).data, 200

        return idempotent(request, f"configuration.{obj.__class__.__name__}.{obj.pk}.deactivate", operation)


class DepartmentAdminViewSet(NoDeleteAdminViewSet):
    queryset = Department.objects.select_related("hospital")
    serializer_class = DepartmentAdminSerializer


class LocationAdminViewSet(NoDeleteAdminViewSet):
    queryset = Location.objects.select_related("hospital")
    serializer_class = LocationAdminSerializer


class ChamberAdminViewSet(NoDeleteAdminViewSet):
    queryset = Chamber.objects.select_related("location")
    serializer_class = ChamberAdminSerializer


class DoctorAdminViewSet(NoDeleteAdminViewSet):
    queryset = DoctorProfile.objects.select_related("hospital", "user").prefetch_related("departments")
    serializer_class = DoctorAdminSerializer


class MyPatientProfileView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]

    def get_object(self, request):
        return PatientProfile.objects.filter(user=request.user, is_active=True).first()

    def get(self, request):
        profile = self.get_object(request)
        if not profile:
            return Response({"detail": "Patient profile not found.", "code": "not_found"}, status=404)
        return Response(PatientSerializer(profile).data)

    def patch(self, request):
        profile = self.get_object(request)
        if not profile:
            return Response({"detail": "Patient profile not found.", "code": "not_found"}, status=404)
        for forbidden in {"is_active", "email", "full_name", "date_of_birth", "sex", "registration_source"} & set(request.data):
            return Response({"detail": f"{forbidden} cannot be changed here.", "code": "field_not_allowed"}, status=400)

        def operation():
            locked = PatientProfile.objects.select_for_update().get(pk=profile.pk)
            serializer = PatientSerializer(locked, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            audit(request, "patient.profile_updated", locked, "update", {"fields": list(serializer.validated_data)})
            return PatientSerializer(locked).data, 200

        return idempotent(request, f"patient.{profile.pk}.profile.update", operation)


class MyConsentView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def _profile(self, request):
        return PatientProfile.objects.filter(user=request.user, is_active=True).first()

    def get(self, request):
        profile = self._profile(request)
        if not profile:
            return Response({"detail": "Patient profile not found.", "code": "not_found"}, status=404)
        consents = profile.consents.select_related("notice_version").order_by("-created_at", "-id")
        paginator = BoundedPagination()
        page = paginator.paginate_queryset(consents, request, view=self)
        return paginator.get_paginated_response(ConsentSerializer(page, many=True).data)

    def post(self, request):
        profile = self._profile(request)
        if not profile:
            return Response({"detail": "Patient profile not found.", "code": "not_found"}, status=404)
        serializer = ConsentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purpose = serializer.validated_data["purpose"]

        def operation():
            notice_query = PrivacyNoticeVersion.objects.filter(hospital=profile.hospital, is_published=True)
            if serializer.validated_data.get("notice_version_id"):
                notice = notice_query.filter(pk=serializer.validated_data["notice_version_id"]).first()
            elif serializer.validated_data.get("notice_version") == "current":
                notice = Hospital.objects.select_for_update().get(pk=profile.hospital_id).active_privacy_notice
            else:
                notice = notice_query.filter(version=serializer.validated_data.get("notice_version")).first()
            if not notice or not notice.is_published or notice.pk != profile.hospital.active_privacy_notice_id:
                return {"detail": "Privacy notice not found.", "code": "not_found"}, 404
            consent = ConsentRecord.objects.create(
                patient=profile,
                notice_version=notice,
                purpose=purpose,
                decision=serializer.validated_data["decision"],
                channel=ConsentRecord.Channel.SELF_SERVICE,
                actor=request.user,
                request_id=request.request_id,
            )
            if consent.purpose == "email_notifications":
                from communications.models import NotificationPreference

                preference, _ = NotificationPreference.objects.select_for_update().get_or_create(user=request.user)
                preference.appointment_email = consent.decision
                preference.queue_email = consent.decision
                preference.save(update_fields=["appointment_email", "queue_email", "updated_at"])
            audit(request, "consent.recorded", consent, "create", {"purpose": consent.purpose, "decision": consent.decision})
            return ConsentSerializer(consent).data, 201

        return idempotent(request, f"patient.{profile.pk}.consent.{purpose}", operation)


class AdminSettingsView(APIView):
    permission_classes = [IsAdministrator]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def get_object(self):
        return Hospital.objects.filter(is_active=True).first()

    def get(self, request):
        hospital = self.get_object()
        if not hospital:
            return Response({"detail": "Hospital configuration is not available.", "code": "not_configured"}, status=503)
        return Response(HospitalAdminSerializer(hospital).data)

    def patch(self, request):
        hospital = self.get_object()
        if not hospital:
            return Response({"detail": "Hospital configuration is not available.", "code": "not_configured"}, status=503)
        serializer = HospitalAdminSerializer(hospital, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        def operation():
            locked = Hospital.objects.select_for_update().get(pk=hospital.pk)
            locked_serializer = HospitalAdminSerializer(locked, data=request.data, partial=True)
            locked_serializer.is_valid(raise_exception=True)
            fields = (
                "display_name",
                "short_name",
                "tagline",
                "logo_url",
                "timezone",
                "currency",
                "email",
                "phone",
                "address",
                "operational_settings",
            )
            before = safe_model_projection(locked, fields)
            updated = locked_serializer.save()
            audit(
                request,
                "hospital.settings_updated",
                updated,
                "update",
                {"before": before, "after": safe_model_projection(updated, fields)},
            )
            return HospitalAdminSerializer(updated).data, 200

        return idempotent(request, "hospital.settings.update", operation)


class PrivacyNoticeAdminView(APIView):
    permission_classes = [IsAdministrator]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def get(self, request):
        hospital = Hospital.objects.filter(is_active=True).first()
        notices = PrivacyNoticeVersion.objects.filter(hospital=hospital) if hospital else PrivacyNoticeVersion.objects.none()
        return Response(
            [
                {
                    "id": str(item.pk),
                    "version": item.version,
                    "title": item.title,
                    "content": item.content,
                    "effective_at": item.effective_at,
                    "is_published": item.is_published,
                    "is_active": hospital.active_privacy_notice_id == item.pk,
                }
                for item in notices
            ]
        )

    def post(self, request):
        serializer = PrivacyNoticeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def operation():
            hospital = Hospital.objects.select_for_update().filter(is_active=True).first()
            if not hospital:
                return {"detail": "Hospital configuration is not available.", "code": "not_configured"}, 503
            data = serializer.validated_data.copy()
            activate = data.pop("publish_and_activate")
            notice = PrivacyNoticeVersion.objects.create(hospital=hospital, is_published=activate, **data)
            if activate:
                hospital.active_privacy_notice = notice
                hospital.save(update_fields=["active_privacy_notice", "updated_at"])
            audit(request, "privacy_notice.created", notice, "create", {"version": notice.version, "published": activate})
            return {
                "id": str(notice.pk),
                "version": notice.version,
                "title": notice.title,
                "effective_at": notice.effective_at,
                "is_published": notice.is_published,
                "is_active": activate,
            }, 201

        return idempotent(request, "privacy_notice.create", operation)


class ReceptionPatientListCreateView(APIView):
    permission_classes = [IsReceptionOrAdmin]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response({"detail": "Search text must contain at least two characters.", "code": "invalid_search"}, status=400)
        queryset = PatientProfile.objects.filter(is_active=True)
        if query:
            queryset = queryset.filter(Q(mrn__iexact=query) | Q(phone__iexact=query) | Q(email__iexact=query) | Q(full_name__icontains=query))
        queryset = queryset.order_by("full_name", "id")
        paginator = BoundedPagination()
        patients = paginator.paginate_queryset(queryset, request, view=self)
        audit(request, "patient.search", None, "search", {"query_provided": bool(query), "result_count": len(patients)})
        return paginator.get_paginated_response(PatientSerializer(patients, many=True).data)

    def post(self, request):
        serializer = AssistedPatientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def operation():
            hospital = Hospital.objects.select_for_update().filter(is_active=True).first()
            if not hospital:
                return ({"detail": "Hospital configuration is not available.", "code": "not_configured"}, 503)
            data = serializer.validated_data.copy()
            notice_id = data.pop("privacy_notice_id")
            data.pop("privacy_accepted")
            notice = PrivacyNoticeVersion.objects.filter(
                pk=notice_id,
                hospital=hospital,
                is_published=True,
            ).first()
            if not notice or hospital.active_privacy_notice_id != notice.pk:
                return {"detail": "The active privacy notice must be acknowledged.", "code": "privacy_notice_invalid"}, 400
            patient = PatientProfile.objects.create(
                hospital=hospital,
                registration_source=PatientProfile.RegistrationSource.RECEPTION,
                **data,
            )
            ConsentRecord.objects.create(
                patient=patient,
                notice_version=notice,
                purpose="service_and_privacy_notice",
                decision=True,
                channel=ConsentRecord.Channel.ASSISTED,
                actor=request.user,
                request_id=request.request_id,
            )
            audit(request, "patient.assisted_created", patient, "create", {"mrn": patient.mrn})
            return PatientSerializer(patient).data, 201

        return idempotent(request, "reception.patient.create", operation)


def _patient_identity_values(patient):
    return {
        "full_name": patient.full_name,
        "email": patient.email,
        "phone": patient.phone,
        "date_of_birth": patient.date_of_birth.isoformat(),
        "sex": patient.sex,
        "address": patient.address,
        "is_active": patient.is_active,
    }


class ReceptionPatientCorrectionView(APIView):
    permission_classes = [IsReceptionOrAdmin]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def patch(self, request, patient_id):
        serializer = PatientCorrectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def operation():
            patient = PatientProfile.objects.select_for_update().filter(pk=patient_id, is_active=True).first()
            if not patient:
                return {"detail": "Active patient not found.", "code": "not_found"}, 404
            data = serializer.validated_data.copy()
            reason = data.pop("reason")
            if "email" in data and patient.user_id and data["email"].lower() != patient.user.email:
                return {
                    "detail": "A linked account email requires the account recovery workflow.",
                    "code": "linked_account_email",
                }, 409
            previous = _patient_identity_values(patient)
            for field, value in data.items():
                setattr(patient, field, value)
            patient.save(update_fields=[*data.keys(), "updated_at"])
            if patient.user_id and "full_name" in data:
                patient.user.display_name = patient.full_name
                patient.user.save(update_fields=["display_name", "updated_at"])
            current = _patient_identity_values(patient)
            PatientCorrectionHistory.objects.create(
                patient=patient,
                event=PatientCorrectionHistory.Event.CORRECTED,
                actor=request.user,
                reason=reason,
                previous_values=previous,
                new_values=current,
                request_id=request.request_id,
            )
            audit(request, "patient.corrected", patient, "correct", {"fields": sorted(data)}, reason)
            return PatientSerializer(patient).data, 200

        return idempotent(request, f"patient.{patient_id}.correct", operation)


class ReceptionPatientDeactivateView(APIView):
    permission_classes = [IsReceptionOrAdmin]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request, patient_id):
        serializer = PatientDeactivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def operation():
            patient = PatientProfile.objects.select_for_update().filter(pk=patient_id, is_active=True).first()
            if not patient:
                return {"detail": "Active patient not found.", "code": "not_found"}, 404
            from operations.models import Appointment, QueueTicket

            confirmed_count = patient.appointments.filter(status=Appointment.Status.CONFIRMED).count()
            active_ticket_count = QueueTicket.objects.filter(
                appointment__patient=patient,
                state__in=[
                    QueueTicket.State.WAITING,
                    QueueTicket.State.CALLED,
                    QueueTicket.State.IN_SERVICE,
                    QueueTicket.State.DEFERRED,
                ],
            ).count()
            if confirmed_count or active_ticket_count:
                return {
                    "detail": "Resolve confirmed appointments and active queue tickets before deactivation.",
                    "code": "active_dependencies",
                    "dependencies": {
                        "confirmed_appointments": confirmed_count,
                        "active_queue_tickets": active_ticket_count,
                    },
                }, 409
            previous = _patient_identity_values(patient)
            patient.is_active = False
            patient.save(update_fields=["is_active", "updated_at"])
            if patient.user_id:
                patient.user.role_assignments.filter(role=RoleAssignment.Role.PATIENT, is_active=True).update(is_active=False)
                if not patient.user.role_assignments.filter(is_active=True).exists():
                    patient.user.is_active = False
                    patient.user.save(update_fields=["is_active", "updated_at"])
            current = _patient_identity_values(patient)
            reason = serializer.validated_data["reason"]
            PatientCorrectionHistory.objects.create(
                patient=patient,
                event=PatientCorrectionHistory.Event.DEACTIVATED,
                actor=request.user,
                reason=reason,
                previous_values=previous,
                new_values=current,
                request_id=request.request_id,
            )
            audit(request, "patient.deactivated", patient, "deactivate", {"is_active": False}, reason)
            return PatientSerializer(patient).data, 200

        return idempotent(request, f"patient.{patient_id}.deactivate", operation)


class ReceptionPatientConsentView(APIView):
    permission_classes = [IsReceptionOrAdmin]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request, patient_id):
        serializer = ConsentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purpose = serializer.validated_data["purpose"]

        def operation():
            patient = PatientProfile.objects.select_for_update().filter(pk=patient_id, is_active=True).first()
            if not patient:
                return {"detail": "Active patient not found.", "code": "not_found"}, 404
            hospital = Hospital.objects.select_for_update().get(pk=patient.hospital_id)
            notice_query = PrivacyNoticeVersion.objects.filter(hospital=hospital, is_published=True)
            notice_id = serializer.validated_data.get("notice_version_id")
            notice_version = serializer.validated_data.get("notice_version")
            if notice_id:
                notice = notice_query.filter(pk=notice_id).first()
            elif notice_version == "current":
                notice = hospital.active_privacy_notice
            else:
                notice = notice_query.filter(version=notice_version).first()
            if not notice or not notice.is_published or notice.pk != hospital.active_privacy_notice_id:
                return {"detail": "Privacy notice not found.", "code": "not_found"}, 404
            consent = ConsentRecord.objects.create(
                patient=patient,
                notice_version=notice,
                purpose=purpose,
                decision=serializer.validated_data["decision"],
                channel=ConsentRecord.Channel.ASSISTED,
                actor=request.user,
                request_id=request.request_id,
            )
            if purpose == "email_notifications" and patient.user_id:
                from communications.models import NotificationPreference

                preference, _ = NotificationPreference.objects.select_for_update().get_or_create(user_id=patient.user_id)
                preference.appointment_email = consent.decision
                preference.queue_email = consent.decision
                preference.save(update_fields=["appointment_email", "queue_email", "updated_at"])
            audit(
                request,
                "consent.assisted_recorded",
                consent,
                "create",
                {"purpose": purpose, "decision": consent.decision},
            )
            return ConsentSerializer(consent).data, 201

        return idempotent(request, f"patient.{patient_id}.consent.{purpose}", operation)


class DuplicateCheckView(APIView):
    permission_classes = [IsReceptionOrAdmin]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request):
        serializer = DuplicateCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        filters = Q()
        for field, value in serializer.validated_data.items():
            lookup = "full_name__icontains" if field == "full_name" else field
            filters |= Q(**{lookup: value})
        matches = PatientProfile.objects.filter(filters, is_active=True)[:10]
        safe = [
            {"id": str(item.pk), "mrn": item.mrn, "full_name": item.full_name, "date_of_birth": item.date_of_birth, "masked_phone": f"***{item.phone[-4:]}"}
            for item in matches
        ]
        audit(request, "patient.duplicate_search", None, "search", {"result_count": len(safe)})
        return Response({"possible_matches": safe, "automatic_merge": False})


class ClaimInvitationView(APIView):
    permission_classes = [IsReceptionOrAdmin]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "write"

    def post(self, request, patient_id):
        serializer = ClaimInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def operation():
            patient = PatientProfile.objects.select_for_update().filter(pk=patient_id, is_active=True, is_claimed=False).first()
            if not patient:
                return {"detail": "Eligible patient not found.", "code": "not_found"}, 404
            email = User.objects.normalize_email(serializer.validated_data["email"])
            resent = bool(patient.user_id)
            if resent:
                user = User.objects.select_for_update().get(pk=patient.user_id)
                if user.email != email:
                    return {
                        "detail": "The pending claim is linked to another email. Correct the patient identity before sending a new invitation.",
                        "code": "claim_email_change_requires_correction",
                    }, 409
                AccountToken.objects.filter(
                    user=user,
                    purpose=AccountToken.Purpose.CLAIM_PATIENT,
                    used_at__isnull=True,
                ).update(used_at=timezone.now())
                from communications.models import NotificationOutbox

                NotificationOutbox.objects.filter(
                    related_id=patient.pk,
                    template_key="claim_patient",
                    state__in=[NotificationOutbox.State.PENDING, NotificationOutbox.State.FAILED],
                ).update(
                    state=NotificationOutbox.State.DEAD,
                    template_data={"invalidated": True},
                    last_error_category="superseded",
                )
            else:
                if User.objects.filter(email=email).exists():
                    return {"detail": "An account already uses this email.", "code": "email_in_use"}, 409
                user = User.objects.create_user(email, None, display_name=patient.full_name)
                RoleAssignment.objects.create(user=user, role=RoleAssignment.Role.PATIENT)
                patient.user = user
                patient.email = email
                patient.save(update_fields=["user", "email", "updated_at"])
            raw = issue_account_token(user, AccountToken.Purpose.CLAIM_PATIENT, minutes=60)
            from communications.services import enqueue_email

            enqueue_email(email, "claim_patient", {"token": raw}, related_id=patient.pk)
            audit(
                request,
                "patient.claim_invitation_resent" if resent else "patient.claim_invited",
                patient,
                "claim_invitation",
                {"resent": resent},
            )
            body = {"accepted": True, "resent": resent}
            if settings.DEBUG:
                body["development_verification_token"] = raw
            return body, 201

        return idempotent(request, f"patient.{patient_id}.claim_invitation", operation)

from urllib.parse import unquote

from django.utils import timezone
from rest_framework import serializers

from accounts.models import RoleAssignment
from accounts.serializers import StrictSerializer

from .models import Chamber, ConsentRecord, Department, DoctorProfile, Hospital, Location, PatientProfile


class DepartmentPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "name", "description", "display_order")


class HospitalPublicSerializer(serializers.ModelSerializer):
    privacy_notice = serializers.SerializerMethodField()

    class Meta:
        model = Hospital
        fields = ("id", "display_name", "short_name", "tagline", "logo_url", "timezone", "currency", "email", "phone", "address", "privacy_notice")

    def get_privacy_notice(self, obj):
        notice = obj.active_privacy_notice
        return (
            {"id": str(notice.pk), "version": notice.version, "title": notice.title, "content": notice.content, "effective_at": notice.effective_at}
            if notice
            else None
        )


class DoctorPublicSerializer(serializers.ModelSerializer):
    departments = DepartmentPublicSerializer(many=True, read_only=True)

    class Meta:
        model = DoctorProfile
        fields = ("id", "doctor_code", "display_name", "designation", "registration_reference", "biography", "consultation_fee_minor", "departments")


class DepartmentAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "hospital", "name", "description", "display_order", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class LocationAdminSerializer(serializers.ModelSerializer):
    code = serializers.CharField(max_length=12, required=True)

    class Meta:
        model = Location
        fields = ("id", "hospital", "name", "code", "address", "phone", "email", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_code(self, value):
        value = value.strip().upper()
        if not value.isascii() or not value.isalnum() or len(value) > 12:
            raise serializers.ValidationError("Use 1 to 12 uppercase ASCII letters or digits.")
        return value


class ChamberAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chamber
        fields = ("id", "location", "name", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class DoctorAdminSerializer(serializers.ModelSerializer):
    department_ids = serializers.PrimaryKeyRelatedField(source="departments", many=True, queryset=Department.objects.all(), write_only=True)
    departments = DepartmentPublicSerializer(many=True, read_only=True)

    class Meta:
        model = DoctorProfile
        fields = (
            "id",
            "hospital",
            "user",
            "doctor_code",
            "display_name",
            "designation",
            "registration_reference",
            "biography",
            "consultation_fee_minor",
            "department_ids",
            "departments",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        hospital = attrs.get("hospital", getattr(self.instance, "hospital", None))
        departments = attrs.get("departments")
        selected_departments = list(departments) if departments is not None else list(self.instance.departments.all()) if self.instance else []
        resulting_active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        if hospital and not hospital.is_active and resulting_active:
            raise serializers.ValidationError({"hospital": ["An active doctor must belong to the active hospital."]})
        if any(department.hospital_id != hospital.id for department in selected_departments):
            raise serializers.ValidationError({"department_ids": ["Every department must belong to the selected hospital."]})
        if resulting_active and not selected_departments:
            raise serializers.ValidationError({"department_ids": ["Select at least one active department."]})
        if resulting_active and any(not department.is_active for department in selected_departments):
            raise serializers.ValidationError({"department_ids": ["Inactive departments cannot be assigned to an active doctor."]})
        user = attrs.get("user", getattr(self.instance, "user", None))
        if user and resulting_active and (not user.is_active or not user.role_assignments.filter(role=RoleAssignment.Role.DOCTOR, is_active=True).exists()):
            raise serializers.ValidationError({"user": ["The selected user does not have an active doctor role."]})
        return attrs

    def validate_doctor_code(self, value):
        value = value.strip().upper()
        if not value.isascii() or not value.isalnum() or len(value) > 12:
            raise serializers.ValidationError("Use 1 to 12 uppercase ASCII letters or digits.")
        return value


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = (
            "id",
            "mrn",
            "full_name",
            "email",
            "phone",
            "date_of_birth",
            "sex",
            "address",
            "registration_source",
            "is_claimed",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "mrn", "registration_source", "is_claimed", "created_at", "updated_at")


class AssistedPatientCreateSerializer(StrictSerializer):
    full_name = serializers.CharField(max_length=160)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.RegexField(r"^\+[1-9]\d{7,14}$")
    date_of_birth = serializers.DateField()
    sex = serializers.ChoiceField(choices=PatientProfile.Sex.choices)
    address = serializers.CharField(max_length=500)
    privacy_notice_id = serializers.UUIDField()
    privacy_accepted = serializers.BooleanField()

    def validate_date_of_birth(self, value):
        today = timezone.localdate()
        try:
            oldest = today.replace(year=today.year - 130)
        except ValueError:
            oldest = today.replace(year=today.year - 130, day=28)
        if value > today:
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        if value < oldest:
            raise serializers.ValidationError("Date of birth cannot be more than 130 years ago.")
        return value

    def validate_privacy_accepted(self, value):
        if not value:
            raise serializers.ValidationError("The patient must acknowledge the active privacy notice.")
        return value


class PatientCorrectionSerializer(StrictSerializer):
    full_name = serializers.CharField(max_length=160, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.RegexField(r"^\+[1-9]\d{7,14}$", required=False)
    date_of_birth = serializers.DateField(required=False)
    sex = serializers.ChoiceField(choices=PatientProfile.Sex.choices, required=False)
    address = serializers.CharField(max_length=500, required=False)
    reason = serializers.CharField(max_length=500)

    def validate_date_of_birth(self, value):
        return AssistedPatientCreateSerializer().validate_date_of_birth(value)

    def validate(self, attrs):
        if not set(attrs) - {"reason"}:
            raise serializers.ValidationError("Provide at least one patient field to correct.")
        return attrs


class PatientDeactivateSerializer(StrictSerializer):
    reason = serializers.CharField(max_length=500)


class DuplicateCheckSerializer(StrictSerializer):
    full_name = serializers.CharField(max_length=160, required=False)
    email = serializers.EmailField(required=False)
    phone = serializers.RegexField(r"^\+[1-9]\d{7,14}$", required=False)
    date_of_birth = serializers.DateField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one approved search field.")
        return attrs


class ConsentCreateSerializer(StrictSerializer):
    notice_version_id = serializers.UUIDField(required=False)
    notice_version = serializers.CharField(max_length=40, required=False)
    purpose = serializers.ChoiceField(choices=["email_notifications"], default="email_notifications")
    decision = serializers.BooleanField(required=False)
    granted = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if "decision" not in attrs and "granted" not in attrs:
            raise serializers.ValidationError({"decision": ["A consent decision is required."]})
        if "decision" in attrs and "granted" in attrs and attrs["decision"] != attrs["granted"]:
            raise serializers.ValidationError({"decision": ["Conflicting consent decisions were provided."]})
        if not attrs.get("notice_version_id") and not attrs.get("notice_version"):
            raise serializers.ValidationError({"notice_version": ["A notice version is required."]})
        attrs["decision"] = attrs.get("decision", attrs.get("granted"))
        return attrs


class ConsentSerializer(serializers.ModelSerializer):
    notice_version = serializers.CharField(source="notice_version.version")
    granted = serializers.BooleanField(source="decision")

    class Meta:
        model = ConsentRecord
        fields = ("id", "notice_version", "purpose", "decision", "granted", "channel", "created_at")


class HospitalAdminSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="display_name", required=False)
    default_slot_duration_minutes = serializers.IntegerField(min_value=5, max_value=60, required=False, write_only=True)
    late_arrival_minutes = serializers.IntegerField(min_value=0, max_value=180, required=False, write_only=True)
    patient_cancellation_cutoff_minutes = serializers.IntegerField(min_value=0, max_value=1440, required=False, write_only=True)

    class Meta:
        model = Hospital
        fields = (
            "id",
            "name",
            "display_name",
            "short_name",
            "tagline",
            "logo_url",
            "timezone",
            "currency",
            "email",
            "phone",
            "address",
            "default_slot_duration_minutes",
            "late_arrival_minutes",
            "patient_cancellation_cutoff_minutes",
            "operational_settings",
            "updated_at",
        )
        read_only_fields = ("id", "operational_settings", "updated_at")

    def to_internal_value(self, data):
        if isinstance(data, dict) and "operational_settings" in data:
            raise serializers.ValidationError({"operational_settings": ["Use the validated top-level settings fields."]})
        return super().to_internal_value(data)

    def update(self, instance, validated_data):
        settings = dict(instance.operational_settings)
        for key in ("default_slot_duration_minutes", "late_arrival_minutes", "patient_cancellation_cutoff_minutes"):
            if key in validated_data:
                settings[key] = validated_data.pop(key)
        validated_data["operational_settings"] = settings
        return super().update(instance, validated_data)

    def validate_timezone(self, value):
        if value != "Asia/Dhaka":
            raise serializers.ValidationError("The pilot uses Asia/Dhaka.")
        return value

    def validate_currency(self, value):
        if value.upper() != "BDT":
            raise serializers.ValidationError("The pilot records BDT only.")
        return "BDT"

    def validate_logo_url(self, value):
        if not value:
            return ""
        decoded = unquote(value)
        if (
            not value.startswith("/")
            or value.startswith("//")
            or "\\" in value
            or "?" in value
            or "#" in value
            or any(ord(character) < 32 for character in value)
            or any(segment in {".", ".."} for segment in decoded.split("/"))
        ):
            raise serializers.ValidationError("Use a safe same-origin absolute path beginning with one slash.")
        return value

    def validate_short_name(self, value):
        value = value.strip().upper()
        if not value.isascii() or not value.isalnum() or not 2 <= len(value) <= 12:
            raise serializers.ValidationError("Use 2 to 12 uppercase ASCII letters or digits.")
        if self.instance and value != self.instance.short_name and self.instance.patients.exists():
            raise serializers.ValidationError("The short name cannot change after the first medical record number.")
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["default_slot_duration_minutes"] = instance.operational_settings.get("default_slot_duration_minutes", 20)
        data["late_arrival_minutes"] = instance.operational_settings.get("late_arrival_minutes", 15)
        data["patient_cancellation_cutoff_minutes"] = instance.operational_settings.get("patient_cancellation_cutoff_minutes", 0)
        return data


class PrivacyNoticeCreateSerializer(StrictSerializer):
    version = serializers.CharField(max_length=40)
    title = serializers.CharField(max_length=180)
    content = serializers.CharField()
    effective_at = serializers.DateTimeField()
    publish_and_activate = serializers.BooleanField()

    def validate(self, attrs):
        if not attrs["publish_and_activate"]:
            raise serializers.ValidationError({"publish_and_activate": ["A new immutable notice must be published and activated when created."]})
        if attrs["effective_at"] > timezone.now():
            raise serializers.ValidationError({"effective_at": ["An active privacy notice cannot take effect in the future."]})
        return attrs


class ClaimInvitationSerializer(StrictSerializer):
    email = serializers.EmailField()

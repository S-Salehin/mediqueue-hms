from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AdminSettingsView,
    ChamberAdminViewSet,
    ClaimInvitationView,
    DepartmentAdminViewSet,
    DepartmentPublicView,
    DoctorAdminViewSet,
    DoctorPublicDetailView,
    DoctorPublicListView,
    DuplicateCheckView,
    HospitalPublicView,
    LocationAdminViewSet,
    MyConsentView,
    MyPatientProfileView,
    PrivacyNoticeAdminView,
    ReceptionPatientConsentView,
    ReceptionPatientCorrectionView,
    ReceptionPatientDeactivateView,
    ReceptionPatientListCreateView,
)

router = SimpleRouter()
router.register("admin/departments", DepartmentAdminViewSet)
router.register("admin/locations", LocationAdminViewSet)
router.register("admin/chambers", ChamberAdminViewSet)
router.register("admin/doctors", DoctorAdminViewSet)

urlpatterns = [
    path("public/hospital/", HospitalPublicView.as_view()),
    path("public/departments/", DepartmentPublicView.as_view()),
    path("public/doctors/", DoctorPublicListView.as_view()),
    path("public/doctors/<uuid:doctor_id>/", DoctorPublicDetailView.as_view()),
    path("me/patient-profile/", MyPatientProfileView.as_view()),
    path("me/consents/", MyConsentView.as_view()),
    path("admin/settings/", AdminSettingsView.as_view()),
    path("admin/privacy-notices/", PrivacyNoticeAdminView.as_view()),
    path("admin/departments/<uuid:pk>/deactivate/", DepartmentAdminViewSet.as_view({"post": "deactivate"})),
    path("admin/locations/<uuid:pk>/deactivate/", LocationAdminViewSet.as_view({"post": "deactivate"})),
    path("admin/chambers/<uuid:pk>/deactivate/", ChamberAdminViewSet.as_view({"post": "deactivate"})),
    path("admin/doctors/<uuid:pk>/deactivate/", DoctorAdminViewSet.as_view({"post": "deactivate"})),
    path("reception/patients/", ReceptionPatientListCreateView.as_view()),
    path("reception/patients/duplicate-check/", DuplicateCheckView.as_view()),
    path("reception/patients/<uuid:patient_id>/", ReceptionPatientCorrectionView.as_view()),
    path("reception/patients/<uuid:patient_id>/consents/", ReceptionPatientConsentView.as_view()),
    path("reception/patients/<uuid:patient_id>/deactivate/", ReceptionPatientDeactivateView.as_view()),
    path("reception/patients/<uuid:patient_id>/claim-invitations/", ClaimInvitationView.as_view()),
    path("", include(router.urls)),
]

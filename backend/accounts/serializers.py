from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from core.exceptions import Conflict

from .models import RoleAssignment, User


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: ["Unknown field."] for key in sorted(unknown)})
        return super().to_internal_value(data)


class LoginSerializer(StrictSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class MFAVerifySerializer(StrictSerializer):
    code = serializers.CharField(min_length=6, max_length=32, trim_whitespace=True)


class MFAReplacementStartSerializer(StrictSerializer):
    current_password = serializers.CharField(trim_whitespace=False, write_only=True)


class RegisterSerializer(StrictSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)
    full_name = serializers.CharField(max_length=160)
    phone = serializers.RegexField(r"^\+[1-9]\d{7,14}$")
    date_of_birth = serializers.DateField()
    sex = serializers.ChoiceField(choices=["female", "male", "other", "unspecified"])
    address = serializers.CharField(max_length=500)
    privacy_notice_id = serializers.UUIDField()
    privacy_accepted = serializers.BooleanField()

    def validate_email(self, value):
        value = User.objects.normalize_email(value)
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account already uses this email.")
        return value

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

    def validate_password(self, value):
        candidate = User(
            email=User.objects.normalize_email(self.initial_data.get("email", "")),
            display_name=self.initial_data.get("full_name", ""),
        )
        validate_password(value, user=candidate)
        return value

    def validate_privacy_accepted(self, value):
        if not value:
            raise serializers.ValidationError("The privacy notice must be accepted to register.")
        return value

    def validate(self, attrs):
        from directory.models import PatientProfile

        if PatientProfile.objects.filter(email__iexact=attrs.get("email", "")).exists() or PatientProfile.objects.filter(phone=attrs.get("phone", "")).exists():
            raise Conflict("A patient record may already exist. Contact reception to claim the existing record.", code="existing_patient_record")
        return attrs


class TokenSerializer(StrictSerializer):
    token = serializers.CharField(min_length=32, max_length=256, trim_whitespace=False)


class ForgotPasswordSerializer(StrictSerializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(TokenSerializer):
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_password(self, value):
        validate_password(value)
        return value


class ClaimPatientAcceptSerializer(TokenSerializer):
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_password(self, value):
        validate_password(value)
        return value


class InvitationCreateSerializer(StrictSerializer):
    email = serializers.EmailField()
    display_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=[choice[0] for choice in RoleAssignment.Role.choices if choice[0] != RoleAssignment.Role.PATIENT])


class InvitationAcceptSerializer(StrictSerializer):
    token = serializers.CharField(min_length=32, max_length=256, trim_whitespace=False)
    display_name = serializers.CharField(max_length=160)
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_password(self, value):
        candidate = User(display_name=self.initial_data.get("display_name", ""))
        validate_password(value, user=candidate)
        return value

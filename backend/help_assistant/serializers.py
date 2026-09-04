from rest_framework import serializers

from accounts.serializers import StrictSerializer


class ConversationTurnSerializer(StrictSerializer):
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField(min_length=1, max_length=800, trim_whitespace=True)


class AssistantQuestionSerializer(StrictSerializer):
    message = serializers.CharField(min_length=2, max_length=600, trim_whitespace=True)
    history = ConversationTurnSerializer(many=True, required=False)

    def validate_history(self, value):
        if len(value) > 6:
            raise serializers.ValidationError("Keep at most six recent conversation turns.")
        return value

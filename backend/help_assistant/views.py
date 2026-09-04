from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAuthenticatedWithStaffMFA
from core.throttling import DatabaseScopedRateThrottle

from .serializers import AssistantQuestionSerializer
from .services import answer_question


class AssistantChatView(APIView):
    permission_classes = [IsAuthenticatedWithStaffMFA]
    throttle_classes = [DatabaseScopedRateThrottle]
    throttle_scope = "assistant"

    def post(self, request):
        serializer = AssistantQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(answer_question(request.user, **serializer.validated_data))

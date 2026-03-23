from __future__ import annotations

from athena_knowledge_mcp.core.exceptions import ConfigurationRequiredError
from athena_knowledge_mcp.core.models import ConfigurationStatus
from athena_knowledge_mcp.services.onboarding_service import OnboardingService


def require_configuration(onboarding_service: OnboardingService) -> ConfigurationStatus:
    status = onboarding_service.get_configuration_status()
    if not status.is_configured:
        raise ConfigurationRequiredError(
            status.missing_fields,
            guidance=status.next_step,
        )
    return status

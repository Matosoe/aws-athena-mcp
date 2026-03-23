from __future__ import annotations

from typing import Any

import boto3  # type: ignore[import-untyped]

from athena_knowledge_mcp.core.models import (
    AwsAuthenticationType,
    AwsSecretMaterial,
    ResolvedConfig,
)


class AwsSessionService:
    fallback_region_name = "us-east-1"

    def build_session(
        self,
        configuration: ResolvedConfig,
        secrets: AwsSecretMaterial,
    ) -> boto3.session.Session:
        kwargs: dict[str, Any] = {"region_name": configuration.aws_region}

        if (
            configuration.authentication_type == AwsAuthenticationType.PROFILE
            and configuration.aws_profile
        ):
            kwargs["profile_name"] = configuration.aws_profile
        elif configuration.authentication_type in {
            AwsAuthenticationType.ACCESS_KEY,
            AwsAuthenticationType.SESSION_TOKEN,
        }:
            kwargs["aws_access_key_id"] = secrets.aws_access_key_id
            kwargs["aws_secret_access_key"] = secrets.aws_secret_access_key
            if configuration.authentication_type == AwsAuthenticationType.SESSION_TOKEN:
                kwargs["aws_session_token"] = secrets.aws_session_token

        return boto3.session.Session(**kwargs)

    def build_client(
        self,
        service_name: str,
        configuration: ResolvedConfig,
        secrets: AwsSecretMaterial,
    ) -> Any:
        session = self.build_session(configuration, secrets)
        return session.client(
            service_name,
            region_name=configuration.aws_region,
        )

    def list_s3_buckets(
        self,
        configuration: ResolvedConfig | None = None,
        secrets: AwsSecretMaterial | None = None,
    ) -> list[str]:
        if configuration is None:
            session = boto3.session.Session(region_name=self.fallback_region_name)
            client = session.client(
                "s3",
                region_name=self.fallback_region_name,
            )
        else:
            client = self.build_client(
                "s3",
                configuration,
                secrets or AwsSecretMaterial(),
            )

        response: dict[str, Any] = client.list_buckets()
        return sorted(
            bucket_name
            for bucket in response.get("Buckets", [])
            if isinstance(bucket, dict)
            and isinstance(bucket_name := bucket.get("Name"), str)
            and bucket_name.strip()
        )

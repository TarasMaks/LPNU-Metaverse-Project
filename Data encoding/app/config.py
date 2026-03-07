"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Image Encryption Service"
    debug: bool = False

    # Transformer key-derivation parameters
    transformer_embed_dim: int = 256
    transformer_num_heads: int = 8
    transformer_num_layers: int = 4
    transformer_key_length: int = 32  # bytes

    # Diffusion encryption parameters
    diffusion_timesteps: int = 50
    diffusion_beta_start: float = 0.0001
    diffusion_beta_end: float = 0.02

    # HMAC integrity
    hmac_algorithm: str = "sha256"

    # Upload limits
    max_image_size_mb: int = 20

    model_config = {"env_prefix": "ENC_"}


settings = Settings()

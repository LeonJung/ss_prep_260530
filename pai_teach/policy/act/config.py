"""Translate `pai_teach/configs/act.yaml` into a LeRobot ACTConfig.

LeRobot's module layout has churned several times across releases; we try the
known import paths in order and fall back to a clear error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ACTRunConfig:
    """Our own config object — independent of LeRobot's evolving API."""

    # dataset
    repo_id: str
    dataset_root: Path
    image_keys: list[str]

    # ACT hyperparameters (will be passed into LeRobot's ACTConfig)
    chunk_size: int
    n_action_steps: int
    n_obs_steps: int
    dim_model: int
    dim_feedforward: int
    n_heads: int
    n_encoder_layers: int
    n_decoder_layers: int
    dropout: float
    pre_norm: bool

    use_vae: bool
    latent_dim: int
    n_vae_encoder_layers: int
    kl_weight: float

    vision_backbone: str
    replace_final_stride_with_dilation: bool
    pretrained_backbone_weights: str | None

    # Optimization / loop
    optimizer_lr: float
    optimizer_lr_backbone: float
    optimizer_weight_decay: float
    batch_size: int
    num_workers: int
    training_steps: int
    save_every: int
    log_every: int
    seed: int

    output_dir: Path
    device: str

    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ACTRunConfig":
        cfg = yaml.safe_load(Path(path).read_text())
        ds = cfg["dataset"]
        return cls(
            repo_id=ds["repo_id"],
            dataset_root=Path(ds["root"]),
            image_keys=list(ds["image_keys"]),
            chunk_size=int(cfg["chunk_size"]),
            n_action_steps=int(cfg["n_action_steps"]),
            n_obs_steps=int(cfg["n_obs_steps"]),
            dim_model=int(cfg["dim_model"]),
            dim_feedforward=int(cfg["dim_feedforward"]),
            n_heads=int(cfg["n_heads"]),
            n_encoder_layers=int(cfg["n_encoder_layers"]),
            n_decoder_layers=int(cfg["n_decoder_layers"]),
            dropout=float(cfg["dropout"]),
            pre_norm=bool(cfg["pre_norm"]),
            use_vae=bool(cfg["use_vae"]),
            latent_dim=int(cfg["latent_dim"]),
            n_vae_encoder_layers=int(cfg["n_vae_encoder_layers"]),
            kl_weight=float(cfg["kl_weight"]),
            vision_backbone=str(cfg["vision_backbone"]),
            replace_final_stride_with_dilation=bool(
                cfg["replace_final_stride_with_dilation"]
            ),
            pretrained_backbone_weights=cfg.get("pretrained_backbone_weights"),
            optimizer_lr=float(cfg["optimizer_lr"]),
            optimizer_lr_backbone=float(cfg["optimizer_lr_backbone"]),
            optimizer_weight_decay=float(cfg["optimizer_weight_decay"]),
            batch_size=int(cfg["batch_size"]),
            num_workers=int(cfg["num_workers"]),
            training_steps=int(cfg["training_steps"]),
            save_every=int(cfg["save_every"]),
            log_every=int(cfg["log_every"]),
            seed=int(cfg["seed"]),
            output_dir=Path(cfg["output_dir"]),
            device=str(cfg["device"]),
            raw=cfg,
        )


# ---------------------------------------------------------------------------
# LeRobot lookup — done lazily so the dev box can import this module without
# torch installed.

def _import_lerobot() -> tuple[type, type, type]:
    """Return (ACTConfig, ACTPolicy, LeRobotDataset) from whichever module path is current."""
    errors: list[Exception] = []
    for cfg_path, pol_path, ds_path in (
        (
            "lerobot.common.policies.act.configuration_act",
            "lerobot.common.policies.act.modeling_act",
            "lerobot.common.datasets.lerobot_dataset",
        ),
        (
            "lerobot.policies.act.configuration_act",
            "lerobot.policies.act.modeling_act",
            "lerobot.datasets.lerobot_dataset",
        ),
    ):
        try:
            cfg_mod = __import__(cfg_path, fromlist=["ACTConfig"])
            pol_mod = __import__(pol_path, fromlist=["ACTPolicy"])
            ds_mod = __import__(ds_path, fromlist=["LeRobotDataset"])
            return cfg_mod.ACTConfig, pol_mod.ACTPolicy, ds_mod.LeRobotDataset
        except ImportError as e:
            errors.append(e)
    raise ImportError(
        "Could not locate LeRobot ACT / dataset modules. "
        "Install via the docker image or requirements-training.txt. "
        f"Tried paths errored with: {errors}"
    )

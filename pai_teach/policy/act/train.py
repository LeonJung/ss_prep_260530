"""ACT training loop on top of LeRobot.

Bridges our `ACTRunConfig` (YAML) to LeRobot's ACTConfig/ACTPolicy and runs
a vanilla single-GPU loop. Intentionally minimal: no DDP, no compile, no
fancy LR schedule. ACT itself is small (~50M params) and converges in a few
hours on a single mid-range GPU.

For sanity runs, override `training_steps` from the CLI (--steps 50).
"""

from __future__ import annotations

import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from .config import ACTRunConfig, _import_lerobot


def _set_seed(seed: int) -> None:
    import random

    import numpy as np

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _build_act_config(run_cfg: ACTRunConfig, dataset) -> object:
    """Construct LeRobot's ACTConfig from our run config + dataset features."""
    ACTConfig, _, _ = _import_lerobot()

    # LeRobot's ACTConfig auto-derives input/output feature shapes from the
    # dataset's `features` (after creation it's available as a property).
    # We pass our hyperparameters as direct kwargs and let LeRobot fill in
    # the rest from the dataset.
    common_kwargs = dict(
        chunk_size=run_cfg.chunk_size,
        n_action_steps=run_cfg.n_action_steps,
        n_obs_steps=run_cfg.n_obs_steps,
        dim_model=run_cfg.dim_model,
        dim_feedforward=run_cfg.dim_feedforward,
        n_heads=run_cfg.n_heads,
        n_encoder_layers=run_cfg.n_encoder_layers,
        n_decoder_layers=run_cfg.n_decoder_layers,
        dropout=run_cfg.dropout,
        pre_norm=run_cfg.pre_norm,
        use_vae=run_cfg.use_vae,
        latent_dim=run_cfg.latent_dim,
        n_vae_encoder_layers=run_cfg.n_vae_encoder_layers,
        kl_weight=run_cfg.kl_weight,
        vision_backbone=run_cfg.vision_backbone,
        replace_final_stride_with_dilation=run_cfg.replace_final_stride_with_dilation,
        pretrained_backbone_weights=run_cfg.pretrained_backbone_weights,
        optimizer_lr=run_cfg.optimizer_lr,
        optimizer_lr_backbone=run_cfg.optimizer_lr_backbone,
        optimizer_weight_decay=run_cfg.optimizer_weight_decay,
    )
    # LeRobot recently moved to `input_features` / `output_features` dicts
    # built from the dataset's stored features. Try the modern path first.
    try:
        from lerobot.configs.types import FeatureType, PolicyFeature  # type: ignore

        input_features = {}
        output_features = {}
        for key, feat in dataset.features.items():
            shape = tuple(feat["shape"])
            if key == "action":
                output_features[key] = PolicyFeature(type=FeatureType.ACTION, shape=shape)
            elif key.startswith("observation.images."):
                input_features[key] = PolicyFeature(type=FeatureType.VISUAL, shape=shape)
            elif key == "observation.state":
                input_features[key] = PolicyFeature(type=FeatureType.STATE, shape=shape)
        return ACTConfig(
            input_features=input_features,
            output_features=output_features,
            **common_kwargs,
        )
    except ImportError:
        # Older LeRobot — uses input_shapes/output_shapes dicts.
        input_shapes: dict[str, list[int]] = {}
        output_shapes: dict[str, list[int]] = {"action": [dataset.features["action"]["shape"][0]]}
        for key, feat in dataset.features.items():
            if key.startswith("observation.images.") or key == "observation.state":
                input_shapes[key] = list(feat["shape"])
        return ACTConfig(
            input_shapes=input_shapes,
            output_shapes=output_shapes,
            **common_kwargs,
        )


def _load_dataset(run_cfg: ACTRunConfig):
    _, _, LeRobotDataset = _import_lerobot()
    # LeRobotDataset(repo_id, root) loads an existing dataset from disk.
    return LeRobotDataset(repo_id=run_cfg.repo_id, root=run_cfg.dataset_root)


def train(run_cfg: ACTRunConfig, override_steps: int | None = None) -> Path:
    """Run training. Returns the directory the final checkpoint was written to."""
    _set_seed(run_cfg.seed)

    device = torch.device(run_cfg.device if torch.cuda.is_available() or run_cfg.device == "cpu" else "cpu")
    if run_cfg.device == "cuda" and device.type == "cpu":
        print("[train_act] WARNING: cuda requested but unavailable — falling back to CPU")

    dataset = _load_dataset(run_cfg)
    act_cfg = _build_act_config(run_cfg, dataset)

    _, ACTPolicy, _ = _import_lerobot()
    policy = ACTPolicy(act_cfg, dataset_stats=getattr(dataset, "stats", None))
    policy.to(device)
    policy.train()

    loader = DataLoader(
        dataset,
        batch_size=run_cfg.batch_size,
        shuffle=True,
        num_workers=run_cfg.num_workers,
        pin_memory=device.type == "cuda",
        drop_last=True,
    )

    optimizer = torch.optim.AdamW(
        [
            {
                "params": [p for n, p in policy.named_parameters() if "backbone" not in n],
                "lr": run_cfg.optimizer_lr,
            },
            {
                "params": [p for n, p in policy.named_parameters() if "backbone" in n],
                "lr": run_cfg.optimizer_lr_backbone,
            },
        ],
        weight_decay=run_cfg.optimizer_weight_decay,
    )

    output_dir = run_cfg.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    total_steps = override_steps if override_steps is not None else run_cfg.training_steps
    step = 0
    data_iter = iter(loader)
    t0 = time.monotonic()
    while step < total_steps:
        try:
            batch = next(data_iter)
        except StopIteration:
            data_iter = iter(loader)
            batch = next(data_iter)

        batch = {k: v.to(device, non_blocking=True) if torch.is_tensor(v) else v for k, v in batch.items()}
        out = policy.forward(batch)
        loss = out["loss"] if isinstance(out, dict) else out
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()

        step += 1
        if step % run_cfg.log_every == 0 or step == 1:
            dt = time.monotonic() - t0
            print(f"[train_act] step {step}/{total_steps}  loss={loss.item():.4f}  ({dt:.1f}s elapsed)")
        if step % run_cfg.save_every == 0:
            ckpt = output_dir / f"step_{step:07d}"
            ckpt.mkdir(exist_ok=True)
            policy.save_pretrained(ckpt)
            print(f"[train_act] saved checkpoint -> {ckpt}")

    final = output_dir / "final"
    final.mkdir(exist_ok=True)
    policy.save_pretrained(final)
    print(f"[train_act] done — final checkpoint at {final}")
    return final

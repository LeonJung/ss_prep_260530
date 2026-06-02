"""Dev-PC-safe tests: no rclpy, no lerobot, no torch.

Validates that the contract layer (robot.yaml + types.py + writer feature spec)
is internally consistent. The training PC runs the full integration separately.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from pai_teach.data_recorder.lerobot_writer import CameraInfo, LeRobotWriter
from pai_teach.ros2_bridge.types import Action, Observation, RobotState

CONFIG_PATH = Path(__file__).parent.parent / "pai_teach" / "configs" / "robot.yaml"


def _cfg() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def test_robot_yaml_loads_and_dimensions_match() -> None:
    cfg = _cfg()
    assert cfg["ur10e"]["dof"] == len(cfg["ur10e"]["joint_names"]) == 6
    assert cfg["dg5f"]["dof"] == len(cfg["dg5f"]["joint_names"]) == 20
    assert len(cfg["cameras"]) >= 1
    for cam in cfg["cameras"]:
        for key in ("name", "topic", "width", "height", "rate_hz"):
            assert key in cam, f"camera missing key: {key}"


def test_observation_and_action_dataclasses() -> None:
    state = RobotState(
        ur10e_position=np.zeros(6, dtype=np.float32),
        ur10e_velocity=np.zeros(6, dtype=np.float32),
        dg5f_position=np.zeros(20, dtype=np.float32),
        dg5f_velocity=np.zeros(20, dtype=np.float32),
        dg5f_effort=np.zeros(20, dtype=np.float32),
    )
    obs = Observation(
        state=state, images={"wrist_cam": np.zeros((480, 640, 3), dtype=np.uint8)}
    )
    action = Action(
        ur10e_position=np.zeros(6, dtype=np.float32),
        dg5f_position=np.zeros(20, dtype=np.float32),
    )
    assert obs.state.ur10e_position.shape == (6,)
    assert action.dg5f_position.shape == (20,)
    assert obs.images["wrist_cam"].shape == (480, 640, 3)


def test_writer_feature_schema_matches_config() -> None:
    cfg = _cfg()
    cams = [
        CameraInfo(name=c["name"], height=int(c["height"]), width=int(c["width"]))
        for c in cfg["cameras"]
    ]
    writer = LeRobotWriter(
        repo_id="test/dummy",
        root="/tmp/pai_teach_test_unused",
        fps=int(cfg["record_rate_hz"]),
        ur10e_joint_names=cfg["ur10e"]["joint_names"],
        dg5f_joint_names=cfg["dg5f"]["joint_names"],
        cameras=cams,
    )
    feats = writer._features()
    assert feats["observation.state"]["shape"] == (26,)
    assert feats["action"]["shape"] == (26,)
    for cam in cams:
        key = f"observation.images.{cam.name}"
        assert key in feats
        assert feats[key]["shape"] == (cam.height, cam.width, 3)


def test_act_yaml_loads_with_consistent_image_keys() -> None:
    """ACTRunConfig parses, and its image_keys match cameras in robot.yaml."""
    from pai_teach.policy.act.config import ACTRunConfig

    act_cfg = ACTRunConfig.from_yaml(
        Path(__file__).parent.parent / "pai_teach" / "configs" / "act.yaml"
    )
    cam_names_in_robot = {c["name"] for c in _cfg()["cameras"]}
    assert set(act_cfg.image_keys) == cam_names_in_robot, (
        f"act.yaml image_keys {act_cfg.image_keys} != "
        f"robot.yaml cameras {sorted(cam_names_in_robot)}"
    )
    assert act_cfg.chunk_size == act_cfg.n_action_steps, (
        "vanilla ACT: n_action_steps should equal chunk_size"
    )
    assert act_cfg.n_obs_steps == 1, "ACT consumes one observation per chunk"


def test_writer_feature_schema_dg5f_off() -> None:
    """When dg5f is disabled, state/action collapse to UR-only 6-dim."""
    cfg = _cfg()
    cams = [
        CameraInfo(name=c["name"], height=int(c["height"]), width=int(c["width"]))
        for c in cfg["cameras"]
    ]
    writer = LeRobotWriter(
        repo_id="test/dummy_no_dg5f",
        root="/tmp/pai_teach_test_unused_2",
        fps=int(cfg["record_rate_hz"]),
        ur10e_joint_names=cfg["ur10e"]["joint_names"],
        dg5f_joint_names=[],  # disabled
        cameras=cams,
    )
    feats = writer._features()
    assert feats["observation.state"]["shape"] == (6,)
    assert feats["action"]["shape"] == (6,)


def test_recorder_state_to_action_lag_one() -> None:
    """Smoke-test the t->t+1 mapping logic used inside Recorder."""
    from pai_teach.data_recorder.recorder import _state_to_action

    state = RobotState(
        ur10e_position=np.arange(6, dtype=np.float32),
        ur10e_velocity=np.zeros(6, dtype=np.float32),
        dg5f_position=np.arange(20, dtype=np.float32),
        dg5f_velocity=np.zeros(20, dtype=np.float32),
        dg5f_effort=np.zeros(20, dtype=np.float32),
    )
    obs = Observation(state=state)
    action = _state_to_action(obs)
    assert np.array_equal(action.ur10e_position, state.ur10e_position)
    assert np.array_equal(action.dg5f_position, state.dg5f_position)
    # Must be a copy, not an alias.
    action.ur10e_position[0] = 999.0
    assert state.ur10e_position[0] == 0.0

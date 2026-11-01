# pai_teach_sim 이전 공지

이 디렉토리의 모든 내용은 **2026-11-01**에 별도 레포로 분리되었습니다.

- **New home**: https://github.com/LeonJung/study_sim
- **Clone**: `git clone https://github.com/LeonJung/study_sim.git ~/study_sim`

Teleop/직접교사 쪽 코드는 계속 ai_ws 에 있습니다 (`colcon_ws/`, `hand_ws/`, `pai_teach/`).

Green-screen DR plan 문서는 `ai_ws/docs/GREEN_SCREEN_DR_PLAN.md` 에 그대로 유지 — 이 문서는 teleop 과 sim 양쪽에 걸쳐 있습니다.

과거 이력은 ai_ws git log 로 참조 (f11901b 이전).

---

## 레포 분리 이유

| 축 | ai_ws | study_sim |
|---|---|---|
| 실로봇 하드웨어 | UR10E + dg5f (slave), VIVE + Manus (master) | 없음 |
| 핵심 스택 | ROS 2 + colcon + LeRobot (ACT) | Isaac Sim + Isaac Lab + GR00T |
| 데이터 플로우 | teleop → dataset → ACT 학습 | sim rollout → RL post-train / RFM eval |
| 작업 PC | 이 PC (dev) + NUC + 학습 PC | Sim PC (Blackwell) + Train PC (B300) |

sim 축의 Docker 레이어, Isaac Sim 환경, GR00T RL 코드가 ai_ws 안에 섞이면 (1) teleop/sim 두 축이 커질수록 디렉토리가 어지러워지고, (2) sim 축을 공개 레포로 올리기 위해 서브트리 split 이 필요해지므로, 분리가 더 깔끔.

컨테이너 내부 경로 (`/workspace/pai_teach_sim`), python 패키지 이름 (`pai_sim`), pyproject project 이름 (`pai_teach_sim`) 은 그대로 유지 — 과거 문서/메모리의 참조 호환성 보존.

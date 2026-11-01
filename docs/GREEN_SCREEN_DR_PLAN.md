# Green-Screen Background Randomization Plan
_(pai_teach_sim — Dexmate Vega + Robotiq 2F 밸브 회전 RL, sim-only 학습/평가)_

> **상태:** 계획(planning) 문서. 개발 미착수. 사용자 승인 후 실행.
> **관련:** [PHYSICAL_AI_OPS.md](./PHYSICAL_AI_OPS.md) §17 (통합 아키텍처 확정안), [ARCHITECTURE.md](./ARCHITECTURE.md), [MULTI_PC_SETUP.md](./MULTI_PC_SETUP.md)
> **최종 갱신:** 2026-09-18

---

## §0. 목적

Physical AI 훈련의 sim→real 시각 gap을 **배경 이미지 축**에서 정면 흡수하기 위한 "특이한 방법"의 설계 문서. 사용자가 별도로 특허 등록한 개념을 sim 파이프라인에 구현하는 계획.

- **훈련(Bed A)**: Isaac Sim/Isaac Lab 상에서 Dexmate Vega가 배관 밸브를 90° 회전
- **평가(Bed B)**: 동일 물리 씬, **다른 배경 이미지 세트**에서 성공률 측정
- **핵심 트릭**: sim rollout 중에는 그린스크린을 pure chroma green으로 렌더 → **후처리(on-the-fly compositor)에서 카메라 pose 기반 homography warp로 실사 배경을 합성** → policy는 배경 무관하게 밸브 조작만 학습

---

## §1. 컨셉: Green-Screen Background Randomization

### §1.1 왜 그린스크린을 sim 안에 두는가

일반적 domain randomization은 씬 전체 텍스처를 procedural random으로 채운다. 이 접근은:

1. **씬 대부분은 정적**(콘크리트 바닥, 배관, 밸브) — 실제 자동화 적용처와 형태·재질이 유사한 부분
2. **그린스크린 평면 뒤편만 실사 이미지 분포**로 스와핑
3. 나중에 real world에서도 물리 그린스크린을 세워 chroma key로 대응 → **sim↔real 대칭 조건**

### §1.2 왜 sim rollout 중이 아니라 후처리인가

**사용자 원안 (정정된 이해):**
- Sim 실행 중 카메라는 그린 배경 그대로 얻음 (텍스처 스왑 X)
- 데이터 저장 시 카메라 pose까지 함께 기록
- **학습 dataloader / RL step 직전에** 폴더의 랜덤 배경 이미지를 **pose 기반 projective warp**로 합성

**장점:**
| 항목 | 효과 |
|---|---|
| Sim 씬 정적 | rollout FPS↑, USD 파일 단순 |
| 데이터 증폭 | 같은 rollout → 배경 N개로 N배 학습 데이터 |
| 결정적 재현 | seed로 배경-에피소드 매핑 고정 가능 |
| 로봇 팔 occlusion | 팔은 chroma green이 아님 → 자동 mask |
| Real 전이 | real에서 물리 그린스크린 + 동일 compositor 재사용 가능 |

### §1.3 특허 정합성 — 역방향 접근 (2026-09-18 확정)

**방침:** 청구항 텍스트를 미리 정렬하는 대신, **본 프로젝트 개발 산출물을 특허 청구항 채우기용 근거 자료로 활용** (역방향).

- 사용자 특허 URL (`claude.ai/artifact/...`)은 외부 fetch 불가 (세션 로그인 필요)
- 개발 진행 자체엔 지연 없음: 우리는 대화로 정립한 개념("그린스크린 pure green 렌더 + pose 기반 homography warp 후처리 합성")대로 구현
- 산출물이 청구항 실시례(embodiment) 근거로 쓰이도록 다음을 문서화:
  - Compositor 알고리즘 정확한 pseudo-code (§5.2)
  - Chroma key + homography 조합의 정합성 증명 (unit test 결과)
  - Bed A→B 성능 gap 지표 (§8) — 트릭의 효과 입증 자료
  - 재현 가능한 seed·데이터·코드 (Gitea + MLflow + DVC)
- 향후: 사용자가 청구항 확정 시 diff 리뷰만 수행

---

## §2. 씬 정의

### §2.1 물리 씬 (Bed A / Bed B 공통)

| 요소 | 스펙 | 비고 |
|---|---|---|
| 바닥 | 흰색-회색 콘크리트, 약한 광택 | roughness ≈ 0.6, 스페큘러 약간 |
| 배관 | 수직, 지름 11 cm, 높이 250 cm, 바닥에서 위로 한 줄기 | material: 도장 강관 |
| 밸브 | 3~5 스포크 알루미늄 handwheel, 지름 17 cm, **빨간 도장**, 배관 옆으로 stem 돌출 | 회전축: 배관축 수직 (수평), target 90° |
| 그린스크린 | 배관 뒤편 평면, **높이 250 cm × 너비 1000 cm**, chroma-green #00B140. **배관 뒤 200 cm (Vega 기준 260 cm)** | pure diffuse, roughness 1.0, emissive 0 |
| 조명 | 실내 균일광 + 약한 directional | 후처리 chroma detection 안정성 목적으로 강한 하이라이트 회피 |

**카메라 가시 영역 계산 (head cam):**
```
거리 260 cm, FoV 60°
→ 가시 너비 = 2 × 260 × tan(30°) ≈ 300 cm
→ 그린스크린 1000 cm 중 중앙 약 300 cm만 head cam에 보임
```
평면을 1000 cm로 크게 잡은 것은 wrist cam이 기울어질 때나 DR로 base가 흔들릴 때도 그린이 화면을 덮도록 하는 여유분.

**밸브 배치:**
- **핸들 중심 높이: 지면 기준 120 cm** (배관 축 상 120 cm 지점에서 stem이 수평 돌출)
- Stem이 로봇을 향하는 방향(y+ 방향) 고정
- Stem 길이(배관 표면에서 handwheel 뒷면까지): TBD (§11 이슈 4)

### §2.2 Bed A ↔ Bed B 차이

**물리는 완전 동일**. 차이는 배경 이미지 풀뿐:
```
assets/backgrounds/
├── bed_a/   ← 학습 세션에서 샘플링
└── bed_b/   ← 평가 전용 (학습 시 노출 절대 금지)
```
- Bed B 이미지 접근을 학습 코드에서 차단 (경로 화이트리스트)
- 두 세트의 이미지 분포(장면 카테고리, 조도, 색 histogram)를 비슷하게 유지하되 실제 픽셀은 겹치지 않도록 큐레이션

---

## §3. 로봇 / 그리퍼 / 카메라

### §3.1 로봇 자산 (확정)

- **Dexmate Vega**: `dexmate-urdf` (GitHub `dexmate-ai/dexmate-urdf`, Apache 2.0)
  - **변형 확정: `vega_1u` (upper body only)** — 밸브 회전은 정지 조작, mobile base 불필요
- **그리퍼: Robotiq 2F-85** (Q11 확정) — `ros-industrial/robotiq` URDF 조달
  - 스트로크 85 mm — handwheel 스포크/rim 두께 10~20 mm 파지에 충분
- **손목 어댑터 (2026-09-18 확정):**
  - 알루미늄 디스크 **직경 60 mm, 두께 10 mm**
  - Vega `L_ee` / `R_ee` 링크에 **fixed joint** 부착 (sim에선 물리 영향 미미)
  - 마운팅 기준: ISO 9409-1-50-4-M6 플랜지 가정
- **USD 변환**: `Isaac Sim URDF Importer` (fixed joint, collision mesh convex decomp 옵션 확인)

### §3.2 카메라 3개 (확정)

| 카메라 | 위치 | 모달리티 | 소스 |
|---|---|---|---|
| head | Vega head | **RGB + depth** (Q12 확정) | ZED (URDF 내장 프레임 활용) |
| wrist L | 좌 gripper 링크 | RGB | 커스텀 프레임 추가 |
| wrist R | 우 gripper 링크 | RGB | 커스텀 프레임 추가 |

**Compositor 적용 범위:** RGB만. Head depth는 그린스크린 평면의 실제 depth 값 그대로 (policy에 강한 기하 힌트).

**해상도/FoV:** 224×224, FoV 60° (3 카메라 공통).

**손목 카메라 프레임 배치 (2026-09-18 확정, eye-in-hand 표준):**
```
position (gripper base 링크 기준): x=0, y=-0.04, z=0.05    # 뒤 40 mm, 위 50 mm
orientation: pitch -25°                                     # 파지점 방향 응시
```
파지 순간 그리퍼 핑거 + 밸브 스포크가 함께 프레임에 들어오는 각도.

---

## §4. RL 태스크 정의

### §4.1 알고리즘 (GR00T backbone 확정, 2026-09-18)

**Policy backbone: GR00T N1.7** (`NVIDIA/Isaac-GR00T`)
- 이유: `PHYSICAL_AI_OPS.md §17` SS17 GR00T 전환 결정 반영 (π0 폐기)
- Vega가 humanoid embodiment class에 속함 → GR00T가 원 target
- Language conditioning 가능 ("turn valve 90 degrees")

**학습 방식 (Exp별 상이, §12A 참조):**
- **SFT (supervised fine-tune)**: 시연 데이터로 policy fine-tune (표준 GR00T workflow)
- **선택적 RL fine-tune**: SFT 후 sparse-reward RL (PPO on `rsl_rl`)로 boost — Isaac Lab 통합
- 시연 원천은 실험별 다름 (§12A)

### §4.2 Observation

```
obs = {
  "rgb_head":    (H, W, 3) uint8,   # compositor 통과 후
  "depth_head":  (H, W, 1) float,   # compositor 미적용, 원본 그대로
  "rgb_wristL":  (H, W, 3) uint8,   # compositor 통과 후
  "rgb_wristR":  (H, W, 3) uint8,   # compositor 통과 후
  "joint_pos":   (14,) float,       # 양팔 7+7
  "joint_vel":   (14,) float,
  "ee_pose_L":   (7,) float,        # xyz + quat
  "ee_pose_R":   (7,) float,
  "gripper_L":   (1,) float,        # 0~1
  "gripper_R":   (1,) float,
}
```

### §4.3 Action

- **양팔 협동** (사용자 확정): 각 팔 joint velocity 7 + gripper 1 = **16 dim**
- 대안: EE cartesian velocity (6+1)×2 = 14 dim (더 낮은 차원, IK 부담)
- 초기 안: joint velocity — Isaac Lab actuator wrapper로 저수준 제어

### §4.4 Reward (초기 안, 튜닝 필요)

```
r_approach = -||ee_L - handle_grasp_L||  - ||ee_R - handle_grasp_R||
r_contact  = +α if both grippers touching handle spokes
r_rotate   = +β * (valve_angle - valve_angle_prev)   # target: 90°
r_success  = +Γ once valve_angle >= π/2
r_penalty  = -δ * torque_regularization
```
- 양손이 스포크 대칭 위치를 잡고 함께 회전시키는 것을 유도
- Curriculum: 초기에는 approach만, 이후 rotate weight 증가

### §4.5 Termination

- Success: valve_angle ≥ 90°
- Timeout: T_max steps
- Failure: 밸브 slip (gripper contact 손실 + rotate 진행 0)

### §4.6 Domain Randomization (배경 외)

- 밸브 마찰 계수 (revolute joint damping)
- 밸브 초기 각도 (±5°)
- Vega base pose 미세 흔들림 (±2 cm, ±1°)
- 조명 강도/색온도
- **배경**: §5에서 상세

### §4.7 LOTO 배제

자물쇠·태그·잠금장치 asset·태스크는 **포함하지 않음** (사용자 확정). 순수 밸브 회전만.

---

## §5. Compositor 설계

### §5.1 실행 방식: **on-the-fly**

RL step 사이에서 GPU 파이프라인으로 실시간 chroma+warp 수행. 사전 렌더 저장 X (초기 안).

### §5.2 파이프라인

```
Isaac Sim render (RGB, green bg)  ─┐
Camera extrinsic (world→cam) 4×4   │
Camera intrinsic K (fx,fy,cx,cy)   ├─→ GPU Compositor  ─→ policy input
Greenscreen plane world corners    │      1. project plane corners → image
  (4 pts, from scene metadata)     │      2. compute H (kornia)
Assigned bg image (per-episode)    ┘      3. warp bg via H
                                          4. chroma mask (HSV green range)
                                          5. mask * warped_bg + (1-mask) * rgb
```

### §5.3 구현 스택

- **PyTorch + kornia**: `kornia.geometry.transform.warp_perspective`
- **Chroma mask**: HSV 공간, H ∈ [138°, 155°], S > 0.5, V > 0.3 (Isaac 렌더 조명 튜닝 후 실측 fine-tune)
- **Anti-alias 처리**: chroma edge에서 배경 반투명 blending (feather 1~2 px)

### §5.4 성능 고려

| 병렬 env | 카메라 해상도 | 이 PC(RTX 2080 8GB) | 학습 WS(Blackwell 96GB) |
|---|---|---|---|
| 4~8 | 128×128 | 가능 (sanity check) | 여유 |
| 64~128 | 224×224 | 불가 | 여유 |
| 256+ | 224×224 | 불가 | 목표 |

---

## §6. 배경 이미지 관리

### §6.1 폴더 구조 (2026-09-18 생성 완료)

```
~/study_sim/  (github.com/LeonJung/study_sim)
├── scripts/fetch_bg_images.py       # Commons 카테고리 순회 수집기
└── assets/backgrounds/
    ├── README.md                    # 장별 라이선스·저작자·해상도 기록 (자동 생성)
    ├── bed_a/  20장  13 MB          # 학습
    └── bed_b/  10장  6.5 MB         # 평가 (unseen, 학습 코드에서 접근 차단)
```

> 2026-11-01 분리: 이 트리는 과거 `ai_ws/pai_teach_sim/` 서브트리였으며, 별도 레포 `study_sim` 으로 뽑혀 나감. python 패키지(`pai_sim`) 및 pyproject project(`pai_teach_sim`) 네이밍은 유지.

**현재 채워진 내용 (임시 placeholder):** Wikimedia Commons **카테고리 순회**로 수집한 산업시설 실내 사진 30장. 전량 tier 0 라이선스 (Public domain 16 / CC0 11 / No restrictions 3) — 저작자 표기 의무 없음. 두 풀은 sha256 기준 disjoint 검증 완료.

**수집기 설계 메모 (`scripts/fetch_bg_images.py`):**
- **키워드 검색이 아니라 카테고리 순회.** 검색은 도면 스캔·건물 외관·야외 사진이 대량 혼입됨(첫 시도에서 유효 후보 1/250). 카테고리(`Machine rooms`, `Boiler rooms`, `Piping`, `Interiors of factories` 등 14개 루트 + subcat 1단계)로 바꾸니 855장 확보
- subcat blocklist로 무관 카테고리 배제 (missile / observatory / office / drawing 등)
- 화질 필터: 채도 평균, hue 엔트로피(세피아 배제), 밝기 상한(도면 배제). PD 필터는 1929년 이전 흑백 아카이브로 쏠리는 경향이 있어 필수
- 사용자가 실제 적용처 B 사진을 확보하면 이 placeholder를 교체할 것

### §6.2 이미지 요건 (샘플 분석 반영, 2026-09-18)

**사용자 제공 샘플:** `docs/img/bg_sample_plant.png` (1983×793 px, 종횡비 **2.50:1**)
- 내용: 산업 플랜트 기계실 — 배관·펌프·탱크 늘어선 복도, 광택 콘크리트 바닥
- **중요: 배경에 빨간 밸브 handwheel이 여러 개 존재** → **distractor로 작동**. Policy가 "배경 밸브"와 "전경 타겟 밸브"를 구분해야 함. 난이도↑, 실전 정합성↑

**요건 (샘플 기준으로 확정):**
- 해상도: 최소 1600×640 (샘플이 1983×793). **단 현재 placeholder는 1280×512로 완화** — Commons PD 풀에서 1600폭 이상 + 실내 산업설비 조건을 동시에 만족하는 장수가 부족했음
- 형식: PNG/JPG (sRGB)
- **내용: 산업 시설 위주로 큐레이션** (아무 이미지가 아님 — 실제 적용처 분포를 흉내)
- 종횡비: 2~3:1 권장 (§6.2a 매핑 정책이 흡수). **현재 placeholder는 대부분 1.33~1.5:1** — §6.2a mirror 확장 폭이 샘플 기준보다 커짐

### §6.2a 이미지 → 그린스크린 평면 매핑 정책 (2026-09-18 확정)

그린스크린은 4:1 (1000×250), 이미지는 2.5:1 → 불일치 해소 방법:

```
1. 이미지를 높이 250 cm에 맞춰 원본 비율 유지 스케일
   2.50:1 → 250 cm 높이 → 625 cm 너비
2. 그린스크린 중앙 625 cm 구간에 배치
3. 좌우 187.5 cm씩은 horizontal mirror로 seamless 확장
4. head cam 가시 범위(중앙 300 cm)는 원본 영역 안 → mirror는 거의 안 보임
```
**이유:** stretch(왜곡)·crop(정보 손실) 없이 디테일 보존. Mirror는 seam이 자연스러움.

**종횡비별 원본 커버 폭 (높이 250 cm 고정, head cam 가시 폭 300 cm):**

| 원본 비율 | 스케일 후 폭 | 가시 범위 커버? |
|---|---|---|
| 2.50:1 (사용자 샘플) | 625 cm | 여유 |
| 1.50:1 | 375 cm | 여유 |
| 1.33:1 | 333 cm | 아슬아슬 — 화면 가장자리에서 mirror seam이 보일 수 있음 |

→ 1.33:1 미만은 수집 단계에서 배제 (`ASPECT_MIN = 1.2`는 여유분, 실사용 하한은 1.33).

### §6.2b 원근 표현에 관한 참고

배경 이미지는 강한 원근감(vanishing point)을 가지지만 우리는 이를 **평면 텍스처**로 붙입니다. 결과적으로 "사진이 붙은 벽"처럼 보입니다.

**이것은 버그가 아니라 의도입니다:**
- Policy에게 "배경은 무시하라"고 가르치는 것이 목적
- Real world에서 물리 그린스크린에 프로젝션/인쇄해도 같은 성질
- 카메라가 움직이면 평면은 pose대로 warp되므로 "월드에 고정된 그림"의 일관성은 유지됨

### §6.3 매핑: (a-1) 결정적

```python
bg_paths = sorted(glob(f"{bg_dir}/*.jpg"))
N = len(bg_paths)
def bg_for_episode(episode_id: int, seed: int) -> str:
    idx = hash((seed, episode_id)) % N
    return bg_paths[idx]
```
- `seed`는 학습 세션 시작 시 확정, MLflow param으로 로깅
- 같은 (seed, episode_id) → 동일 배경 → **완전 재현 가능**

### §6.4 버저닝

- **DVC로 배경 이미지 세트 추적** (§17 확정안 정합)
- 배경 세트 hash를 MLflow run tag로 기록

---

## §7. 데이터셋 스키마

**LeRobot v3 확장** (§17 확정안 준수, 필드 추가):

```yaml
per_frame:
  - rgb_head:    HxWx3 uint8       # 초록 배경 원본
  - rgb_wristL:  HxWx3 uint8
  - rgb_wristR:  HxWx3 uint8
  - cam_head_pose_world:    (4,4) float32   # NEW
  - cam_wristL_pose_world:  (4,4) float32   # NEW
  - cam_wristR_pose_world:  (4,4) float32   # NEW
  - joint_pos, joint_vel, ee_poseL, ee_poseR, gripper_L/R, action

per_episode_metadata:
  - cam_head_intrinsics:   (3,3) K matrix   # NEW
  - cam_wristL_intrinsics: (3,3)            # (episode-static)
  - cam_wristR_intrinsics: (3,3)
  - greenscreen_plane_world_corners: (4,3) float32  # NEW
  - greenscreen_plane_normal: (3,) float32          # NEW
  - assigned_bg_path: str  (compositor 결과와 별도)  # NEW
  - success: bool
  - final_valve_angle: float
```

RL 학습이면 정식 dataset이 필요 없을 수 있으나 (rollout이 in-memory) — **evaluation 및 후속 IL(imitation) 확장 대비**로 이 스키마를 유지.

---

## §8. 평가 프로토콜 (Bed A → Bed B)

### §8.1 정량 지표

| 지표 | 정의 |
|---|---|
| Success rate | valve_angle ≥ 90° 도달 비율 |
| Time to success | 성공 rollout 평균 스텝 수 |
| Grasp stability | 밸브 접촉 유지 시간 비율 |
| **Bed A→B gap** | `SR(A) - SR(B)` — 시각 일반화 실패 크기 |

### §8.2 절차

1. **Bed A validation**: 학습 세션 종료 시 A 배경 held-out 20장으로 100 rollout
2. **Bed B eval**: B 배경 전량으로 100 rollout
3. **SimplerEnv Visual Matching 스타일**: 배경 분포 shift 하에서 policy invariance 정량화 (§17 참조)

### §8.3 성공 기준 (계획 목표)

- 초기: SR(A) ≥ 0.8, Bed A→B gap ≤ 0.1
- 이 gap이 우리 접근의 핵심 KPI

---

## §9. 컴퓨트 배치

| 작업 | 이 PC (leon, RTX 2080 8GB) | 학습 WS (Blackwell 96GB) | Jetson Thor |
|---|---|---|---|
| USD 씬 저작 | ⭕ | — | — |
| URDF→USD 변환 | ⭕ (Isaac Sim GUI) | ⭕ | — |
| Compositor 개발/검증 | ⭕ (kornia 단위 테스트) | ⭕ | — |
| Sanity rollout (4~8 env, 128²) | ⚠️ 가능 | 여유 | — |
| **본격 RL 학습 (128+ env, 224²)** | ❌ | ✅ | — |
| Sim eval (Bed A/B rollout) | ❌ | ✅ | — |
| Real deploy inference (TensorRT) | — | — | ✅ (향후) |

**⚠️ 사전 검증 필요:** 이 PC의 RTX 2080(Turing)에서 최신 Isaac Sim이 실제로 뜨는지 (Isaac Sim 5.x가 Turing 지원을 드롭했는지 미확인). 개발 착수 전 필수 체크.

---

## §10. §17 파이프라인과의 정합

| §17 컴포넌트 | 본 계획에서의 역할 |
|---|---|
| Isaac Sim + Isaac Lab | 씬 + RL 환경 (본 계획의 sim layer) |
| MinIO | Rollout 로그, 배경 이미지 세트 저장 |
| MLflow | seed, bg 세트 hash, 하이퍼파라미터, SR(A)/SR(B) 트래킹 |
| DVC | `assets/backgrounds/{bed_a, bed_b}/` 버저닝 |
| Gitea / GitHub | 코드 저장소 (`study_sim` — 과거 `pai_teach_sim`, 2026-11-01 분리) |
| ONNX → TensorRT NVFP4 | 향후 real deploy 시 |
| Jetson Thor | 향후 real deploy target |
| π0 / VLA | 본 계획은 순수 RL. 향후 π0 finetune 확장 시 IL 데이터셋으로 rollout 재활용 |

---

## §11. 오픈 이슈

1. **특허 정합성 확인** — 개발 진행 자체엔 무영향. 청구항 텍스트 확보 시 §1.3 채우고 diff 리뷰 (claude.ai artifact 외부 접근 불가)
2. ~~**Vega URDF 카메라 프레임 실체**~~ — ✅ 확인 완료 (2026-09-18): 머리 ZED 스테레오 내장, 손목은 dexs_gripper에만
3. ~~**밸브 배치 높이**~~ — ✅ 120 cm 확정 (2026-09-18)
4. ~~**밸브 stem 길이**~~ — ✅ 10 cm 확정 (2026-09-18)
5. ~~**양팔 협동 grasp 전략**~~ — ✅ (iii) IL+RL 하이브리드 (2026-09-18). **시연 원천 (α) sim 스크립티드 controller 제안, 승인 대기**
6. ~~**Isaac Sim의 Turing GPU 지원 여부**~~ — ✅ 확인 완료 (2026-09-18): 4.2/4.5도 RTX 3070 minimum, RTX 2080 공식 미지원
7. ~~**배경 이미지**~~ — ✅ 샘플 확보 (2026-09-18) `docs/img/bg_sample_plant.png`. 산업 플랜트 기계실, 2.50:1. 매핑 정책 §6.2a 확정. **남은 것: 실제 pool 이미지 수량 확보 (bed_a/bed_b 분리)**
8. ~~**Compositor edge artifact**~~ — ✅ Simple binary chroma mask로 시작 (2026-09-18)
9. ~~**Vega 베이스 위치·자세**~~ — ✅ 배관 정면 60 cm, 정면 응시 (2026-09-18)
10. ~~**평가에서 DR on/off**~~ — ✅ (i) A/B 모두 base·조명 고정, 배경만 변수 (2026-09-18)
11. ~~**그리퍼 선택**~~ — ✅ (ii) Robotiq 2F 고수 (2026-09-18). URDF는 `ros-industrial/robotiq`
12. ~~**머리 카메라 구성**~~ — ✅ (iii) ZED RGB + depth (2026-09-18)
13. ~~**이 PC 역할**~~ — ✅ Q6 (ii) Isaac Sim 4.5 이 PC 설치 시도 (Phase 0에 배치, 2026-09-18)
14. ~~**Robotiq 2F ↔ Vega 손목 마운트 어댑터**~~ — ✅ 직경 60 mm × 두께 10 mm 알루미늄 디스크, fixed joint (2026-09-18, §3.1)
15. ~~**손목 카메라 커스텀 프레임 위치**~~ — ✅ gripper base 기준 뒤 40 mm·위 50 mm, pitch −25° (2026-09-18, §3.2)
16. ~~**시연 데이터 원천**~~ — ✅ Q5b (2026-09-18): 3안 모두 실행 (Exp A/B/C, §12A)
17. ~~**§17의 π0 결정과 GR00T의 관계**~~ — ✅ SS17 (2026-09-18): GR00T 전환 확정. PHYSICAL_AI_OPS.md §17 갱신 완료
18. **GR00T Vega embodiment adapter** — Phase 0.5에서 `configs/embodiment_vega_robotiq.yaml` 정의:
    - action 16 dim (양팔 joint 7+7 + gripper 2), state (joint_pos 14 + joint_vel 14 + ee_pose 14 + gripper 2)
    - camera keys: `head`, `wrist_left`, `wrist_right`
    - normalization stats는 수집 데이터에서 자동 계산
    - GR00T `new_embodiment` 태그로 등록
19. **⚠️ BLOCKER 후보: Cosmos WFM이 학습 WS GPU 1장(Blackwell 96GB)에서 실행 가능한가**
    - GR00T-Dreams는 내부적으로 Cosmos Predict-2 (video generation) 필요 → VRAM 요구량 큼
    - **96GB로 부족하면 Exp B·Exp C 모두 불가** → Exp A(스크립티드)만 남고 계획 축소
    - Phase 0에서 최우선 검증
20. **그린스크린 배관 뒤 거리** — ✅ 200 cm 확정 (2026-09-18, §2.1)

---

## §12. 개발 순서 (실행 착수 시)

### Phase 0: 검증 (착수 전)
1. **이 PC에서 Isaac Sim 4.5 설치·부팅 시도** (Q6 (ii) 확정, 2026-09-18). 성공 시 씬 저작에도 활용, 실패 시 학습 WS 전담
2. ~~dexmate-urdf 실체 확인~~ ✅ 완료 (2026-09-18)
3. ~~특허 텍스트 정합 검토~~ → 역방향 접근으로 대체 (§1.3)
4. **GR00T-Dreams 실기 데모** — Vega+밸브 씬에 대해 궤적 dream이 유의미한지 학습 WS에서 확인
5. **GR00T N1.7 checkpoint fetch + Vega embodiment adapter 초안** — cross-embodiment fine-tune 가능성 실측

### Phase 1: 씬 & 자산
6. ~~`pai_teach_sim/` 리포 생성 (Gitea)~~ ✅ 완료 (2026-11-01): `github.com/LeonJung/study_sim` 로 분리. ai_ws 서브트리 삭제, `pai_teach_sim_MOVED.md` stub 유지.
7. Vega URDF → USD (`vega_1u` + Robotiq 2F 마운트, 손목 카메라 커스텀 프레임)
8. 밸브·배관·그린스크린·바닥 USD 저작
9. `assets/backgrounds/{bed_a, bed_b}/` 폴더 + CC0/사용자 첨부 이미지

### Phase 2: Compositor
10. `compositor/gs_compositor.py` (kornia 기반)
11. 단위 테스트: 정지 씬 + 임의 배경 → warp 정합 확인 (이 PC RTX 2080에서 충분)

### Phase 3: 공통 RL/IL 환경 골격
12. `tasks/valve_rotation_env.py` (Isaac Lab) — obs/action/reward/term
13. Compositor를 obs 파이프라인에 통합
14. Sanity check (이 PC, 4 env, 128×128)

### §12A. Phase 4~6: 3 실험 (Q5b — GR00T 3안 모두 실행)

**실험 순서 근거:** Exp A는 인프라 baseline → Exp B는 A와 시연만 스왑 (공정 비교) → Exp C는 compositor ablation (특허 트릭 순수 기여 측정).

#### Phase 4: Exp A — (δ-3) 스크립티드 시연 + GR00T + Compositor
15. **스크립티드 controller 구현** — 밸브 handwheel 기하 기반 analytic IK 양팔 궤적 생성
16. Sim rollout → LeRobot v3 dataset (초록 배경)
17. Compositor 적용 → augmented dataset
18. **GR00T N1.7 SFT fine-tune** (학습 WS)
19. (선택) sparse-reward RL fine-tune (PPO on `rsl_rl`)
20. Bed A/B 평가 → `results/exp_a.json`

#### Phase 5: Exp B — (δ-1) Hybrid: GR00T-Dreams 궤적 + Compositor
21. **GR00T-Dreams 실행** (학습 WS, Cosmos WFM) — Vega+밸브 씬 이미지 + "turn valve 90°" 프롬프트
22. 생성된 neural trajectory → sim에서 replay → 우리 씬 카메라로 재렌더 (초록 배경)
23. Compositor 적용 → augmented dataset
24. GR00T N1.7 SFT fine-tune (Exp A와 동일 hyperparameter)
25. Bed A/B 평가 → `results/exp_b.json`

#### Phase 6: Exp C — (δ-2) GR00T-Dreams 그대로 (Compositor 우회)
26. GR00T-Dreams video 그대로 IL 학습 (LAPA-style inverse dynamics 또는 GR00T-Dreams가 제공하는 action)
27. **Compositor 미사용** — dream된 video의 배경 그대로
28. Bed A/B 평가 → `results/exp_c.json`
    - Bed B는 여전히 우리 sim 씬 (씬 자체는 A/B 동일, 배경만 다름). Exp C는 학습 시엔 우리 씬 무관, 평가 시엔 우리 씬 사용 → 배포 정합 위해 필요

### Phase 7: 3 실험 비교 분석
29. 지표 표: SR(A), SR(B), Bed A→B gap, sample efficiency, wall-clock, GPU cost
30. Ablation 결론:
    - Exp A vs Exp B: **시연 원천 효과** (스크립티드 vs GR00T-Dreams)
    - Exp B vs Exp C: **특허 트릭 순수 효과** (compositor 유/무)
31. 결과 문서화 → 특허 청구항 실시례 자료로 정리 (§1.3 역방향 접근)

---

_(문서 끝)_

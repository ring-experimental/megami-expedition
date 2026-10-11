# MEGAMI EXPEDITION — 프로토타입

스팀펑크 × 마법 세계의 3D 웹 RPG 프로토타입 (three.js + Vite + TypeScript).
**필드 액션(하늘의 궤적 리메이크식) → 턴제 패링 전투(33원정대식) → 협상 영입(여신전생식)** 루프를 검증하기 위한 빌드입니다.

```bash
npm install
npm run dev        # http://localhost:5173 (포트가 사용 중이면 다음 빈 포트)
npm run build      # 타입 체크 + 프로덕션 빌드 (dist/)
npm run preview    # 빌드 결과 확인
npm run models     # Blender로 모든 3D 모델 재생성 (Blender 5.2 필요, 경로는 BLENDER=... 로 변경)
```

Node.js 20.19 이상(Vite 7)이 필요합니다.

## 게임 루프

| 단계 | 내용 |
|---|---|
| 필드 | WASD 이동, 약공격 3연타 / 강공격 / 회피. 적의 **브레이크 게이지**(노란 바)를 채우면 기절 → `E`로 **선제 공격** 전투 |
| 전투 진입 | 기절시키고 진입: **아군 선행동 + 적 전원 브레이크 상태** · 적의 돌진/탄에 정면으로 닿음: **공평** · 등 뒤를 맞음: **기습(적 선행동)** |
| 필드 처치 | 약한 적(톱니쥐·보일러 젤리·램프 위스프)은 필드에서 처치 가능 — 보상 50%, **영입 불가**. 강한 적은 브레이크까지만 |
| 턴제 전투 | 속도 기반 턴 순서(CTB), AP(턴마다 +1, 기본 공격 +1, 패링 +1), 스킬 QTE, 적 공격 시 **패링/회피**, 전부 패링하면 자동 반격, 브레이크(1턴 기절 + 받는 피해 1.5배) |
| 협상 | `대화` → 성격별 질문 2개 + 요구(아이템/기어/HP) → 확률 판정. **해당 적에게 성공한 패링 횟수**만큼 영입 확률 상승 |
| 영입 | 파티 = 카이(고정) + 리라 + 영입 몬스터, 전투 참가 3명. **같은 종족을 또 영입하면 기존 동료에게 경험치로 흡수** |
| 난이도 | 스토리/노말/하드 — 패링·회피·QTE 판정 폭, 타이밍 링 표시, 받는 피해. 메뉴(Esc) → 설정에서 언제든 변경 |

저장 기능은 없습니다(새로고침하면 처음부터).

### 조작

- **필드**: `WASD` 이동 · `Shift` 달리기 · 마우스 시점(화면 클릭 시 고정) · 휠 줌 · `좌클릭/J` 약공격 · `우클릭/K` 강공격 · `Space` 회피 · `E` 전투 개시/조사 · `Esc` 메뉴 · `H` 도움말
- **전투**: `W/S` 또는 `1~5` 커맨드 · `A/D` 대상 · `Enter` 결정 · `Esc` 취소 · 적 공격 시 `F/좌클릭` 패링, `Space/우클릭` 회피 · QTE는 `F/Space/좌클릭`
- **게임패드** (Xbox · PlayStation · Switch Pro 표준 배치 — 패드 버튼을 누르면 패드 표기로, 키 입력·마우스 이동·클릭·휠이 있으면 키보드 표기로 모든 화면 안내가 즉시 전환)
  - 필드: `LS` 이동(기울기만큼 속도) · `LB`(누르고 있기)/`L3` 달리기 · `RS` 시점 · `R3` 시점 정면 · 십자 `↑↓` 줌 · `X` 약공격 · `Y` 강공격 · `B` 회피 · `A` 전투 개시/조사 · `Start` 메뉴 · `View` 도움말
  - 전투: 십자/`LS` 선택 · `A` 결정 · `B` 취소 · 적 공격 시 `A/RB` 패링, `B` 회피 · QTE는 `A/B/RB`
  - 메뉴: 십자/`LS` 이동 · `A` 선택 · `B` 닫기/뒤로 · `LB/RB` 탭 전환 · 설정에서 패드 시점 감도 · 진동 on/off
  - 패드가 이상하게 동작하면 메뉴 → 설정 → **입력 장치**에서 브라우저가 인식한 패드·축·버튼을 실시간으로 확인할 수 있습니다.

### 판정 폭 (data/types.ts `DIFFICULTY`)

| | 패링 | 회피 | QTE Perfect / Good | 받는 피해 | 타이밍 링 |
|---|---|---|---|---|---|
| 스토리 | ±160ms | ±260ms | 90 / 200ms | ×0.7 | O |
| 노말 | ±95ms | ±180ms | 60 / 140ms | ×1.0 | O |
| 하드 | ±55ms | ±115ms | 40 / 100ms | ×1.25 | X (명중 직전 섬광만) |

## 그래픽 · 성능

메뉴(Esc) → 설정 → **그래픽**에서 품질과 자동 해상도를 고릅니다. 설정은 브라우저에 저장됩니다.

| 품질 | 렌더 해상도 상한 | 그림자 | 블룸 | 안티에일리어싱 |
|---|---|---|---|---|
| 낮음 | 1.0 MP | 1024 | 끔 | 없음 |
| 보통 | 2.1 MP (1080p급) | 2048 | 켬 | 없음 |
| 높음 | 8.3 MP (4K) | 2048 | 켬 | MSAA 4× |

- **자동 해상도**: 프레임이 계속 45fps 아래면 렌더 해상도를 100 → 85 → 70 → 55%로 낮추고, 여유가 생기면 다시 올립니다.
- **내장 그래픽 감지**: 브라우저가 CPU 내장 그래픽으로 실행 중이면 '낮음'으로 시작하고 안내를 띄웁니다. 외장 그래픽카드가 있다면 Windows 설정 → 시스템 → 디스플레이 → 그래픽에서 브라우저를 **고성능**으로 지정하거나 모니터를 그래픽카드에 연결하세요(`chrome://gpu`의 GL_RENDERER로 확인).
- 일시정지 중에는 3D를 다시 그리지 않습니다.

개발 시 지켜야 할 렌더링 규칙:
- **씬에 `THREE.PointLight`를 추가하지 마세요.** 조명 개수가 바뀌면 모든 셰이더가 재컴파일되어 수백 ms~수 초 멈춥니다. 국소 조명은 `fx.lights.add(new FakeLight(...))`(fx/fakeLights.ts)를 씁니다.
- 셰이더는 로딩 화면에서 미리 컴파일됩니다(`Game.warmUp`). 새 모델·이펙트 종류를 추가하면 warm-up에도 넣어야 첫 사용 때 끊기지 않습니다.
- 이펙트 재질은 `dispose()`하지 않습니다(셰이더 프로그램이 해제되어 다음 사용 때 다시 컴파일됨).
- 모델의 단색 재질 조각들은 로딩 시 하나로 합쳐집니다(core/assets.ts `mergePrimitives`: 색 → 버텍스 컬러, 거칠기/금속성 → `pbr` 속성). 복제한 재질에는 `patchMaterial()`이 적용돼야 합니다.

## 콘텐츠

- 영웅: **카이**(증기검사, 물리) · **리라**(에테르 마도사, 마법/회복)
- 적/영입 가능 몬스터 6종 — 성격이 협상 성향을 결정

| 몬스터 | 등급 | 성격 | 좋아하는 대답 | 약점 |
|---|---|---|---|---|
| 톱니쥐 | 약함 | 겁쟁이 | 다정 | 번개·냉기 |
| 보일러 젤리 | 약함 | 천진 | 유머 | 냉기 |
| 램프 위스프 | 약함 | 호기심 | 논리 | 냉기·물리 |
| 놋쇠 딱정벌레 | 강함 | 고집 | 칭찬 | 번개 |
| 태엽 기사 | 강함 | 기사도 (패링 0회면 확률 반감) | 대담 | 번개 |
| 증기 골렘 | 정예 | 탐욕 (브레이크 또는 HP 50% 이하일 때만 협상) | 요구 수락 | 냉기 |

- 필드 1개(에테르 평원 · 멈춘 시계탑): 적 심볼 13개, 보물상자 4개, 휴식 지점(전체 회복 + 적 재배치)
- 3D 모델: 카이·리라는 로우폴리 플랫 셰이딩, 몬스터·소품·전투 아레나는 하이폴리 스무스 셰이딩

## 구조

```
src/
  main.ts, debug.ts          진입점 / 개발용 콘솔 헬퍼(window.dbg)
  game/   game.ts            렌더러·후처리·모드 전환·루프·셰이더 warm-up
          state.ts           파티·인벤토리·영입·경험치
          graphics.ts        그래픽 품질 프리셋 · 자동 해상도 · 내장 그래픽 감지
  core/   assets.ts          GLB 로드·복제·재질 조각 병합   input.ts  키보드/마우스/게임패드
          audio.ts           WebAudio 합성 효과음            timeline.ts  전투 연출용 게임 시간 스케줄러
  field/  field.ts player.ts fieldEnemy.ts terrain.ts
  battle/ battle.ts bunit.ts battleUI.ts timing.ts(패링·QTE 판정) negotiation.ts
  anim/   rig.ts             스켈레톤 본(이름 기반) 절차적 애니메이션 + 옷자락·꼬리 2차 모션
  data/   units.ts skills.ts items.ts negotiation.ts world.ts types.ts   ← 밸런스/콘텐츠는 여기서 수정
  fx/     effects.ts         파티클·일회성 이펙트(공유 지오메트리)
          fakeLights.ts      PointLight 대체 셰이더 조명(고정 크기 배열 → 재컴파일 없음)
          environment.ts     하늘·원경·부유 입자
  ui/     ui.ts fieldHud.ts menus.ts art.ts(2D 에셋 연결) glyph.ts(키/패드 버튼 표기) padNav.ts(메뉴 패드 내비게이션) controlsHelp.ts
tools/blender/               Blender 5.2 모델 생성·리깅 스크립트
  ASSET_SPEC.md, RIG_SPEC.md 모델 ↔ 게임 코드 규약(노드/본 이름, 피벗, 폴리곤 예산)
  model_<name>.py            캐릭터·몬스터·아레나 (build_characters.sh / build_env.sh 로 일괄 빌드)
  model_props.py             props.glb 조립기 ← props_{nature,steam,small,clocktower,airship}.py
  hp_helpers.py 외           공용 헬퍼 (베벨·스무스+하드엣지·버텍스 AO·GLB export·EEVEE 프리뷰)
  check_glb.py, verify_env.py  내보낸 GLB의 노드·본·폴리곤 검사
  previews/                  렌더 프리뷰 출력 (로컬 전용, git 미포함)
public/models/*.glb          생성된 모델
public/art/                  2D 에셋 (아래 참고)
docs/2D_ASSET_PROMPTS.md     2D 에셋 목록·생성 프롬프트
```

### 개발용 콘솔 (`npm run dev`에서만)

브라우저 탭이 백그라운드여도 고정 스텝으로 게임을 진행할 수 있습니다.

```js
await dbg.battle('s_knight1', 'party')   // 해당 스폰과 즉시 전투 ('party' | 'enemy' | 'none')
await dbg.auto({ parry: true })          // 기본 공격 + 완벽 패링으로 자동 진행
dbg.state.recruit('wisp', 4)             // 강제 영입
await dbg.step(1, true)                  // 1초 진행 후 렌더
```

## 2D 에셋

43개 2D 에셋(로고 · 초상화 · 아이콘)이 모두 `public/art/`에 들어 있습니다. 파일을 정해진 이름으로 교체·추가하면 자동 적용되고(개발 서버 자동 새로고침), 파일이 없으면 이니셜/이모지로 대체됩니다.
용도·생김새·파일명·이미지 생성 프롬프트는 [docs/2D_ASSET_PROMPTS.md](docs/2D_ASSET_PROMPTS.md)에 있습니다.

| 경로 | 용도 |
|---|---|
| `public/art/ui/logo.png` | 타이틀 로고 |
| `public/art/portraits/<id>.png` (+ `_happy`, `_angry`) | 파티 카드 · 턴 순서 · 협상 대화창 · 메뉴 초상화 / 협상 반응 표정 |
| `public/art/icons/cmd_*`, `item_*`, `el_*`, `st_*` | 전투 커맨드 · 아이템 · 속성 · 상태이상 아이콘 |

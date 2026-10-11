# MEGAMI EXPEDITION — 프로토타입

스팀펑크 × 마법 세계의 3D 웹 RPG 프로토타입.
**필드 액션(하늘의 궤적 리메이크식) → 턴제 패링 전투(33원정대식) → 협상 영입(여신전생식)** 루프를 검증하기 위한 빌드입니다.

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # 타입 체크 + 프로덕션 빌드 (dist/)
npm run models     # Blender로 모든 3D 모델 재생성 (Blender 5.2 필요)
```

## 게임 루프

| 단계 | 내용 |
|---|---|
| 필드 | WASD 이동, 약공격 3연타 / 강공격 / 회피. 적의 **브레이크 게이지**(노란 바)를 채우면 기절 → `E`로 **선제 공격** 전투 |
| 전투 진입 | 기절시키고 진입: **아군 선행동 + 적 전원 브레이크 상태** · 적의 돌진/탄에 정면으로 닿음: **공평** · 등 뒤를 맞음: **기습(적 선행동)** |
| 필드 처치 | 약한 적(톱니쥐·보일러 젤리·램프 위스프)은 필드에서 처치 가능 — 보상 50%, **영입 불가**. 강한 적은 브레이크까지만 |
| 턴제 전투 | 속도 기반 턴 순서(CTB), AP(턴마다 +1, 기본 공격 +1, 패링 +1), 스킬 QTE, 적 공격 시 **패링/회피**, 전부 패링하면 자동 반격, 브레이크(1턴 기절 + 받는 피해 1.5배) |
| 협상 | `대화` → 성격별 질문 2개 + 요구(아이템/기어/HP) → 확률 판정. **해당 적에게 성공한 패링 횟수**만큼 영입 확률 상승 |
| 영입 | 파티 = 카이(고정) + 리라 + 영입 몬스터, 전투 참가 3명. **같은 종족을 또 영입하면 기존 동료에게 경험치로 흡수** |
| 그래픽 | 메뉴(Esc) → 설정 → 그래픽: 낮음/보통/높음(렌더 해상도 상한·그림자·블룸·MSAA) + 자동 해상도. 내장 그래픽이 감지되면 '낮음'으로 시작하고 안내 표시 |
| 난이도 | 스토리/노말/하드 — 패링·회피·QTE 판정 폭, 타이밍 링 표시, 받는 피해. 메뉴(Esc) → 설정에서 언제든 변경 |

### 조작

- **필드**: `WASD` 이동 · `Shift` 달리기 · 마우스 시점(화면 클릭 시 고정) · 휠 줌 · `좌클릭/J` 약공격 · `우클릭/K` 강공격 · `Space` 회피 · `E` 전투 개시/조사 · `Esc` 메뉴 · `H` 도움말
- **전투**: `W/S` 또는 `1~5` 커맨드 · `A/D` 대상 · `Enter` 결정 · `Esc` 취소 · 적 공격 시 `F/좌클릭` 패링, `Space/우클릭` 회피 · QTE는 `F/Space/좌클릭`
- **게임패드** (Xbox · PlayStation · Switch Pro 표준 배치 — 패드 버튼을 누르면 패드 표기로, 키 입력·마우스 이동·클릭·휠이 있으면 키보드 표기로 모든 화면 안내가 즉시 전환)
  - 필드: `LS` 이동(기울기만큼 속도) · `LB`(누르고 있기)/`L3` 달리기 · `RS` 시점 · `R3` 시점 정면 · 십자 `↑↓` 줌 · `X` 약공격 · `Y` 강공격 · `B` 회피 · `A` 전투 개시/조사 · `Start` 메뉴 · `View` 도움말
  - 전투: 십자/`LS` 선택 · `A` 결정 · `B` 취소 · 적 공격 시 `A/RB` 패링, `B` 회피 · QTE는 `A/B/RB`
  - 메뉴: 십자/`LS` 이동 · `A` 선택 · `B` 닫기/뒤로 · `LB/RB` 탭 전환 · 설정에서 패드 시점 감도 · 진동 on/off

### 판정 폭 (data/types.ts `DIFFICULTY`)

| | 패링 | 회피 | QTE Perfect / Good | 받는 피해 | 타이밍 링 |
|---|---|---|---|---|---|
| 스토리 | ±160ms | ±260ms | 90 / 200ms | ×0.7 | O |
| 노말 | ±95ms | ±180ms | 60 / 140ms | ×1.0 | O |
| 하드 | ±55ms | ±115ms | 40 / 100ms | ×1.25 | X (명중 직전 섬광만) |

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

## 구조

```
src/
  main.ts, debug.ts          진입점 / 개발용 콘솔 헬퍼(window.dbg)
  game/   game.ts state.ts   렌더러·모드 전환·루프 / 파티·인벤토리·영입·경험치
          graphics.ts       그래픽 품질 프리셋(낮음/보통/높음) · 자동 해상도 · 내장 그래픽 감지
  field/  field.ts player.ts fieldEnemy.ts terrain.ts
  battle/ battle.ts bunit.ts battleUI.ts timing.ts negotiation.ts
  anim/   rig.ts             스켈레톤 본(이름 기반) 절차적 애니메이션 + 옷자락·꼬리 2차 모션
  data/   units.ts skills.ts items.ts negotiation.ts world.ts types.ts   ← 밸런스/콘텐츠는 여기서 수정
  fx/     effects.ts environment.ts fakeLights.ts(PointLight 대신 고정 크기 셰이더 조명 — 런타임 조명 추가로 인한 셰이더 재컴파일 방지)
  ui/     ui.ts fieldHud.ts menus.ts glyph.ts(키/패드 버튼 표기) padNav.ts(메뉴 패드 내비게이션) controlsHelp.ts(입력 장치별 조작법)
tools/blender/               Blender 5.2 모델 생성·리깅 스크립트 (ASSET_SPEC.md / RIG_SPEC.md = 모델↔코드 규약)
  hp_helpers.py              하이폴리 공용 헬퍼 (베벨·스무스+하드엣지·버텍스 AO·COLOR_0 export·EEVEE 프리뷰)
  model_props.py             props.glb 조립기 ← props_{nature,steam,small,clocktower,airship}.py 그룹 모듈
  legacy_lowpoly/            하이폴리 패스 이전의 로우폴리 스크립트·GLB·프리뷰 (비교/롤백용)
public/models/*.glb          생성된 모델 (카이·리라 = 로우폴리 플랫, 나머지 = 하이폴리 스무스, 2026-10-11)
public/art/                  2D 에셋 드롭 위치 (아래 참고)
```

### 개발용 콘솔 (`npm run dev`에서만)

브라우저 탭이 백그라운드여도 고정 스텝으로 게임을 진행할 수 있습니다.

```js
await dbg.battle('s_knight1', 'party')   // 해당 스폰과 즉시 전투 ('party' | 'enemy' | 'none')
await dbg.auto({ parry: true })          // 기본 공격 + 완벽 패링으로 자동 진행
dbg.state.recruit('wisp', 4)             // 강제 영입
await dbg.step(1, true)                  // 1초 진행 후 렌더
```

## 2D 에셋 드롭인

`public/art/` 아래에 정해진 이름으로 파일을 넣기만 하면 자동 적용되고, 없으면 이니셜/이모지로 대체됩니다.
**필요한 43개 에셋의 용도·생김새·파일명·이미지 생성 프롬프트는 [docs/2D_ASSET_PROMPTS.md](docs/2D_ASSET_PROMPTS.md)** 에 있습니다.

| 경로 | 용도 |
|---|---|
| `public/art/ui/logo.png` | 타이틀 로고 |
| `public/art/portraits/<id>.png` (+ `_happy`, `_angry`) | 파티 카드 · 턴 순서 · 협상 대화창 · 메뉴 초상화 / 협상 반응 표정 |
| `public/art/icons/cmd_*`, `item_*`, `el_*`, `st_*` | 전투 커맨드 · 아이템 · 속성 · 상태이상 아이콘 |

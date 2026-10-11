# 2D 에셋 제작 가이드 & 프롬프트

외부 이미지 모델로 만들 2D 에셋 43개의 **용도 · 생김새 · 파일명 · 프롬프트**를 정리했습니다.
파일을 `public/art/` 아래 정해진 이름으로 넣기만 하면 게임에 바로 반영됩니다(개발 서버가 자동 새로고침).
없는 파일은 지금처럼 이니셜 원형이나 이모지로 표시되므로, **우선순위 1부터 조금씩** 넣어도 됩니다.

---

## 0. 전체 목록

| 우선 | 파일 (`public/art/…`) | 개수 | 게임 어디에 나오나 | 실제 표시 크기 |
|---|---|---|---|---|
| ★1 | `ui/logo.png` | 1 | 타이틀 화면 중앙 (움직이는 3D 필드 위) | 가로 최대 760px |
| ★1 | `portraits/kai.png` 외 7종 | 8 | 전투 파티 카드 · 상단 턴 순서 · 협상 대화창 · 메뉴(파티/도감) | 원형 34~46px, 대화창 84px |
| ★2 | `icons/cmd_*.png` | 5 | 전투 커맨드 메뉴(공격/스킬/대화/아이템/도주) | 약 22px |
| ★2 | `icons/item_*.png` | 4 | 아이템 메뉴 · 소지품 · 보물상자/전리품 알림 · 협상 요구 | 약 20px |
| ★2 | `icons/el_*.png` | 5 | 스킬 이름 앞(속성) · 도감 약점/내성 | 약 20px |
| ★2 | `icons/st_*.png` | 7 | 아군 카드/적 HP바 아래 상태이상 | 약 15px |
| ★3 | `portraits/system.png` | 1 | 협상 중 「시스템」 안내 말풍선 | 84px |
| ★3 | `portraits/{몬스터}_happy.png`, `_angry.png` | 12 | 협상 중 반응 표정 (좋은 대답 → happy, 나쁜 대답/거절 → angry) | 84px |
| ★1 | `portraits/cutin_kai.png`, `cutin_lyra.png` | 2 | 전투 컷인 (스킬 · COUNTER) — §7 | 사선 창 170×150px (1080p에서 255×225) |
| ★1 | `ui/gear_ring.png` | 1 | 전투 커맨드 톱니 링 (회전함) — §7 | 152px 원 (1080p 228px) |
| ★2 | `ui/ink_band.png` | 1 | 컷인 뒤를 가로지르는 잉크 붓 띠 — §7 | 화면 폭 × 150px |
| ★2 | `ui/ink_splat.png` | 1 | PARRY · WEAK · BREAK 글자 뒤 잉크 얼룩 — §7 | 약 200×90px |
| ★2 | `ui/target_blade.png` | 1 | 대상 선택 시 적 머리 위에 꽂히는 칼날 표식 — §7 | 26×54px |
| ★3 | `ui/ink_texture.png` | 1 | 먹색 패널 전체의 잉크 결 (타일 반복) — §7 | 256px 타일 |
| ★2 | `ui/feather.png` | 1 | 영입 성공 때 떨어지는 여신의 깃털 — §7 | 34×100px (여러 장이 회전하며 낙하) |
| ★3 | `portraits/cutin_<몬스터>.png` | 6 | 영입한 몬스터가 스킬을 쓸 때 컷인 — §7 | 컷인과 같음 |

> 확장자는 `.png` 권장 (`.webp`도 인식). 파일명은 표의 이름 그대로 저장하세요 (대소문자 무관).

---

## 1. 공통 규칙

### 아트 디렉션
- 게임 속 3D 모델은 **큰 머리의 귀여운(치비) 비율**입니다 (주인공 카이·리라는 로우폴리, 몬스터는 매끈한 하이폴리). 2D는 같은 캐릭터를 그린 **일러스트 버전**으로, *애니메풍 JRPG 일러스트 + 셀 셰이딩 + 부드러운 회화풍 조명*을 기준으로 합니다.
- 색 기조: **놋쇠·구리·철·가죽(따뜻한 금갈색)** + **마법광(시안 `#5ff3ff`, 보라 `#b77bff`, 호박색 `#ffb347`)**.
- **3D 모델 미리보기를 레퍼런스 이미지로 첨부하면 일치도가 크게 올라갑니다.** → `tools/blender/previews/` (로컬에서 `npm run models`로 생성, git 미포함) 의 `kai_face.png`, `lyra_face.png`, `cograt.png`, `slime.png`, `wisp.png`, `beetle.png`, `knight_front.png`, `golem.png`

### 해상도 · 배경
| 종류 | 생성 크기 | 저장 크기 | 배경 |
|---|---|---|---|
| 로고 | 가로형 16:7 (예: 1792×784) | 가로 1600px 이하 | **투명 필수** |
| 초상화 | 1024×1024 | 512×512 | 투명 권장. 안 되면 표에 적힌 **캐릭터 색 단색 배경**(게임도 같은 색 원을 깔기 때문에 그대로 써도 자연스러움) |
| 아이콘 | 1024×1024 | 256×256 | **투명 필수**. 안 되면 흰 단색 배경으로 만들고 배경 제거 툴 사용 |

### 구도 규칙 (중요)
- **초상화는 원형으로 잘립니다.** 얼굴이 정중앙, 머리 끝~어깨까지(바스트샷), 네 모서리에는 중요한 것이 없게.
- 모든 초상화는 **3/4 각도로 화면 오른쪽을 향하게** 통일합니다(대화창·파티 카드가 왼쪽에 있어서 시선이 화면 중앙을 향함).
- **아이콘은 15~22px로 줄어듭니다.** 큰 실루엣 하나, 두꺼운 외곽선, 강한 대비. 글자·잔디테일·테두리 프레임 금지. 결과물을 축소해 24px에서 무엇인지 알아볼 수 있는지 꼭 확인하세요.

### 일관성 팁
1. **카이 초상화를 먼저 완성**하고, 이후 생성마다 그 이미지를 *스타일 레퍼런스*로 첨부합니다 (Midjourney `--sref`, GPT/Gemini: "match the art style of the attached image").
2. 아이콘은 **카테고리별로 한 번에 묶어서**(예: 커맨드 5개를 한 장의 5칸 시트로) 생성한 뒤 잘라내면 스타일이 맞습니다.
3. 표정 변형(★3)은 새로 생성하지 말고 **기본 초상화를 편집**("change only the expression…")해서 만드세요.

### 공통 네거티브 (Stable Diffusion/Flux의 negative prompt, Midjourney의 `--no`)
```
text, letters, watermark, signature, logo, frame, border, multiple characters, cropped face, cut-off head, blurry, lowres, jpeg artifacts, photorealistic, 3d render, extra limbs, deformed hands, busy background
```
(로고에는 `text, letters` 를 빼고 사용)

---

## 2. 타이틀 로고 — `ui/logo.png`

**어떤 이미지인가:** 타이틀 화면 정중앙에 뜨는 게임 제목 로고. 뒤에는 밝은 하늘과 초록 들판(3D)이 천천히 돌아가므로 **어두운 외곽선 + 그림자**로 어떤 배경에서도 읽혀야 합니다.
- 글자: `MEGAMI` (윗줄, 자간 넓게) / `EXPEDITION` (아랫줄, 더 크게). 고전 로마체 대문자(게임 UI 폰트 *Cinzel*과 같은 계열).
- 재질: 광택 나는 놋쇠를 새긴 듯한 금속 글자, 리벳, 베벨.
- 장식: 글자 뒤로 반쯤 보이는 커다란 톱니바퀴 링, 위쪽 중앙에 빛나는 시안색 에테르 결정과 은은한 후광(Megami = 여신), 가장자리에 하얀 증기 몇 가닥.
- **한글 부제(「증기와 에테르의 원정대」)는 넣지 마세요.** 게임이 로고 아래에 HTML로 따로 표시합니다.

```
Video game title logo. A wordmark that reads exactly "MEGAMI EXPEDITION" set in two lines: "MEGAMI" on top with wide letter spacing, "EXPEDITION" below and larger. Bold classical Roman serif capitals in the style of Cinzel ExtraBold, forged from polished engraved brass with beveled edges, small rivets and a warm gold gradient, thick dark bronze outline and a soft drop shadow so it stays legible over a bright sky and green fields. Behind the letters, a large thin brass cogwheel ring is partially visible. At the top center, a small glowing cyan aether crystal radiates a faint goddess-like halo of light rays. A few wisps of white steam curl around the edges. Steampunk fantasy, elegant and heroic, centered symmetrical composition, wide horizontal format 16:7, isolated on a transparent background. No other text, no subtitle, no watermark.
```

**글자가 깨질 때:** 글자 없이 엠블럼만 생성한 뒤(`...Do not include any lettering; leave a wide empty band in the middle for a title.`), 포토샵/피그마에서 *Cinzel ExtraBold* 글꼴에 금색 그라데이션 + 베벨 + 어두운 외곽선을 넣어 합성하는 것이 가장 확실합니다.

---

## 3. 캐릭터 초상화 (★1) — `portraits/<id>.png`

**공통 사용처:** 전투 화면 왼쪽 아래 파티 카드(46px 원), 상단 턴 순서 칩(34~44px 원), 협상 대화창 왼쪽(84px 둥근 사각), 메뉴의 파티 편성/몬스터 도감 카드.
**공통 구도:** 바스트샷, 3/4 각도로 오른쪽을 봄, 얼굴 정중앙, 원형으로 잘려도 안전한 여백.

### 3-1. 카이 — `kai.png` (주인공 · 증기검사 · UI색 `#e2a64a`)
- 18세 전후 소년. **헝클어진 뾰족한 진갈색 머리**, 크고 짙은 갈색 애니메 눈, 볼에 옅은 홍조.
- **이마 위로 올려 쓴 놋쇠 비행 고글**(연하늘색 렌즈).
- **짙은 남색 롱코트**에 놋쇠 견장·놋쇠 단추, 크림색 셔츠, **길게 늘어진 빨간 스카프**.
- 어깨에 등에 멘 소형 놋쇠 증기팩의 가죽 끈, 어깨 뒤로 하얀 증기 한 줄기.
- 표정: 자신감 있고 다정한 반쯤 웃는 얼굴, 결의가 느껴지는 눈.

```
Character portrait for a fantasy steampunk JRPG. Kai, an 18-year-old boy, the hero, a "steam swordsman": messy spiky dark chocolate-brown hair, large dark-brown anime eyes, faint blush on the cheeks, brass aviator goggles with pale-blue lenses pushed up on his forehead, a deep navy-blue long coat with brass epaulettes and brass buttons over a cream shirt, a bright red scarf with a long trailing end, a leather strap of a small brass steam backpack over his shoulder with a thin wisp of white steam rising behind it. Confident, friendly half-smile with determined eyes. Head-and-shoulders bust, three-quarter view turned slightly to the right, face centered with comfortable margin on all sides so it survives a circular crop. Anime-inspired JRPG illustration, clean cel shading with soft painterly lighting, warm golden key light from the upper left and a subtle cyan rim light. Transparent background (if unavailable: flat solid #e2a64a background). Single character, no text, no frame.
```

### 3-2. 리라 — `lyra.png` (고정 동료 · 에테르 마도사 · UI색 `#b77bff`)
- 17세 전후 소녀. **은백색 긴 머리**, 얼굴 옆으로 내려오는 옆머리.
- **보라색 넓은 챙의 마녀 모자** — 놋쇠 모자띠 + 작은 놋쇠 톱니 장식.
- **오른쪽 눈에 놋쇠 외알 안경(모노클)** + 가는 체인.
- **보라색 코트 드레스**, 크림색 앞판과 목의 크림색 리본, 가슴을 가로지르는 갈색 가죽 끈.
- 눈동자는 은은히 빛나는 보라색. 차분하고 지적인, 살짝 장난기 있는 미소.
- 어깨 뒤로 지팡이 머리(놋쇠 톱니 고리 + 빛나는 연보라 결정)가 살짝 보이게.

```
Character portrait for a fantasy steampunk JRPG. Lyra, a 17-year-old girl, an aether mage and artificer: long silver-white hair with locks framing her face, softly glowing violet eyes, a wide-brimmed purple witch hat with a brass hatband and a small brass cogwheel emblem, a brass monocle with a thin chain over her right eye, a purple coat-dress with a cream front panel and a cream bow at the collar, a brown leather strap across her chest. Behind her shoulder, the head of her staff is visible: a brass gear ring holding a glowing pale-violet crystal. Calm, intelligent expression with a slightly mischievous half-smile. Head-and-shoulders bust, three-quarter view turned slightly to the right, face centered with comfortable margin so it survives a circular crop (the tip of the hat may be cut off). Anime-inspired JRPG illustration, clean cel shading with soft painterly lighting, warm golden key light from the upper left and a soft violet magical rim light. Transparent background (if unavailable: flat solid #b77bff background). Single character, no text, no frame.
```

### 3-3. 톱니쥐 — `cograt.png` (약한 적 · 성격 *겁쟁이* · UI색 `#b8673a`)
- **태엽으로 움직이는 기계 쥐.** 구리 몸통에 놋쇠 띠와 리벳, **동그란 놋쇠 귀**(안쪽 구리), **빨갛게 빛나는 눈**, 놋쇠 수염, 검은 코.
- 등에 **놋쇠 태엽 열쇠**, 구슬처럼 마디진 구리 꼬리.
- 표정: 겁먹고 경계하는 얼굴 — 귀가 살짝 처지고, 몸을 움츠림.

```
Creature portrait for a fantasy steampunk JRPG. A "Cog Rat": a small clockwork mechanical rat with a copper body wrapped in brass bands and rivets, big round brass ears with copper insides, glowing red eyes, thin brass whiskers, a black nose, a brass wind-up key sticking out of its back and a segmented bead-like copper tail curling up. Timid personality: nervous, wary expression, ears slightly drooping, body hunched as if ready to flee, cute rather than scary. Bust framing of the head and front body, three-quarter view turned slightly to the right, head centered with comfortable margin so it survives a circular crop. Anime-inspired JRPG illustration, clean cel shading with soft painterly lighting, warm key light from the upper left, red eye glow. Transparent background (if unavailable: flat solid #b8673a background). Single creature, no text, no frame.
```

### 3-4. 보일러 젤리 — `slime.png` (약한 적 · 성격 *천진* · UI색 `#3fd1b8`)
- **반투명한 청록색 젤리 돔**, 안에 **빛나는 시안색 핵**이 비침.
- **눈 대신 놋쇠 압력계 두 개**(흰 눈금판 + 검은 바늘 + 빨간 경고 눈금).
- 꼭대기에 **놋쇠 밸브와 구리 핸들 바퀴**, 거기서 김이 폴폴.
- 표정: 장난기 가득, 바늘이 들뜬 듯 기울어짐, 말랑하게 통통 튀는 느낌.

```
Creature portrait for a fantasy steampunk JRPG. A "Boiler Jelly": a cute translucent teal jelly blob shaped like a dome, with a glowing cyan core visible inside its body, two brass pressure-gauge dials (white faces with black needles and a small red danger mark) serving as its eyes, a brass valve on top with a copper hand-wheel puffing a little white steam. Childish, playful personality: mischievous grin implied by tilted gauge needles, bouncy squishy pose. Bust framing, three-quarter view turned slightly to the right, centered with comfortable margin so it survives a circular crop. Anime-inspired JRPG illustration, clean cel shading with soft painterly lighting, glossy subsurface glow in the jelly, warm key light from the upper left. Transparent background (if unavailable: flat solid #3fd1b8 background). Single creature, no text, no frame.
```

### 3-5. 램프 위스프 — `wisp.png` (약한 적 · 성격 *호기심* · UI색 `#ffb347`)
- **공중에 뜬 육각형 놋쇠 랜턴**(유리창), 안에 **두 개의 작은 눈을 가진 살아 있는 호박색 불꽃 정령**.
- 위에 고리 손잡이, 랜턴 주위를 도는 **가는 놋쇠 고리 두 개**, 양옆에 **작은 놋쇠 톱니 날개**(구리 깃).
- 표정: 호기심 가득 — 불꽃이 앞으로 기울고 눈이 동그래짐.

```
Creature portrait for a fantasy steampunk JRPG. A "Lamp Wisp": a floating hexagonal brass lantern with glass panes, inside it a living amber flame spirit with two small dark curious eyes, a ring handle on top, two thin brass rings orbiting around the lantern, and small brass cogwheel "wings" with copper fins on both sides. Curious personality: the flame leans forward toward the viewer with wide inquisitive eyes. Bust framing of the whole lantern, three-quarter view turned slightly to the right, centered with comfortable margin so it survives a circular crop. Anime-inspired JRPG illustration, clean cel shading with soft painterly lighting, strong warm amber glow from the flame lighting the brass from inside. Transparent background (if unavailable: flat solid #ffb347 background). Single creature, no text, no frame.
```

### 3-6. 놋쇠 딱정벌레 — `beetle.png` (강한 적 · 성격 *고집/자존심* · UI색 `#c9a14a`)
- **반짝이는 놋쇠 갑각의 장수풍뎅이**, **강철 끝이 달린 크게 휜 놋쇠 뿔**.
- 갑각에 구리 리벳 패치, 검은 철 배와 다리(놋쇠 마디), **초록으로 빛나는 눈**.
- 표정/구도: 약간 아래에서 올려다본 앵글, 턱을 치켜든 거만한 자세, 갑각에 반짝 하이라이트.

```
Creature portrait for a fantasy steampunk JRPG. A "Brass Beetle": a rhinoceros beetle with a highly polished brass carapace decorated with copper rivet patches, a large curved brass horn with a sharp steel tip, a black iron underside and legs with brass joints, glowing green eyes. Proud, haughty personality: chin raised, smug posture, a gleaming highlight sparkling on its shell. Slightly low camera angle to make it look imposing. Bust framing of the head, horn and front of the shell, three-quarter view turned slightly to the right, centered with comfortable margin so it survives a circular crop. Anime-inspired JRPG illustration, clean cel shading with soft painterly lighting, warm key light from the upper left, green eye glow. Transparent background (if unavailable: flat solid #c9a14a background). Single creature, no text, no frame.
```

### 3-7. 태엽 기사 — `knight.png` (강한 적 · 성격 *기사도* · UI색 `#8a6a2c`)
- **자동인형 기사.** 검은 철 + 광택 놋쇠 갑옷, **가로 시야창에서 호박색으로 빛나는 눈**이 보이는 통투구.
- 놋쇠 어깨갑, **톱니 문양이 새겨진 놋쇠 흉갑**, **너덜너덜한 진홍색 휘장**.
- 등 뒤로 보이는 **커다란 놋쇠 태엽 열쇠**, 어깨 너머로 할버드 날 끝.
- 표정: 엄숙하고 기품 있는 정면 응시(얼굴이 없으므로 자세와 눈빛으로).

```
Character portrait for a fantasy steampunk JRPG. A "Clockwork Knight": a tall automaton knight in black iron and polished brass plate armor, a great bucket helm with a single horizontal visor slit glowing warm amber, brass pauldrons, a brass breastplate engraved with a cogwheel emblem, a tattered crimson tabard, a large brass wind-up key protruding from its back behind the shoulder, and the blade of a halberd visible over its shoulder. Stoic, honorable, dignified bearing, gazing calmly at the viewer. Head-and-shoulders bust, three-quarter view turned slightly to the right, helm centered with comfortable margin so it survives a circular crop. Anime-inspired JRPG illustration, clean cel shading with soft painterly lighting, warm key light from the upper left and amber glow from the visor. Transparent background (if unavailable: flat solid #8a6a2c background). Single character, no text, no frame.
```

### 3-8. 증기 골렘 — `golem.png` (정예 · 성격 *탐욕* · UI색 `#ffb347`)
- **거대한 증기 골렘.** 검은 철 용광로 몸통에 놋쇠 띠와 리벳, **가슴의 둥근 화로 창살 안에서 호박색 불이 이글거림**.
- 몸에 비해 **아주 작은 돔형 머리**(빛나는 시야창), 거대한 어깨, 등 뒤 **높은 굴뚝에서 연기**.
- 구도: 머리가 작으므로 **머리+가슴 화로까지** 담기. 낮은 앵글로 위압감.
- 표정: 굶주린 탐욕 — 화로 불빛이 침 흘리듯 넘실, 연기를 뿜음.

```
Character portrait for a fantasy steampunk JRPG. A "Steam Golem": a massive furnace golem with a black iron body bound by brass bands and rivets, a round furnace grille in its chest blazing with amber fire, a tiny dome-shaped head with a glowing amber visor slit sitting low between enormous shoulders, a tall chimney stack on its back puffing dark smoke. Greedy, hungry personality: the furnace flickers hungrily and smoke snorts from the chimney. Low camera angle for an imposing look. Bust framing that includes the small head and the glowing chest furnace, three-quarter view turned slightly to the right, centered with comfortable margin so it survives a circular crop. Anime-inspired JRPG illustration, clean cel shading with soft painterly lighting, strong amber firelight from the furnace. Transparent background (if unavailable: flat solid #ffb347 background). Single character, no text, no frame.
```

---

## 4. 아이콘 (★2) — `icons/<종류>_<id>.png`

**공통 아이콘 스타일 문장** (각 프롬프트에 이미 포함됨):
> fantasy steampunk game UI icon, single centered object filling about 80% of the canvas, bold chunky silhouette readable at 24 pixels, hand-painted semi-flat style with cel shading, polished brass and copper with one glowing magical accent color, thick dark-brown outline, soft top-left lighting, no text, no frame, transparent background

**팁:** 같은 종류끼리는 *"a sprite sheet of N icons in a single row, evenly spaced, same style"* 으로 한 장에 생성 → 잘라서 저장하면 통일감이 좋습니다.

### 4-1. 전투 커맨드 아이콘 — `cmd_*.png` (5개)
전투 오른쪽 아래 커맨드 메뉴의 각 줄 앞에 붙습니다.

| 파일 | 메뉴 | 그림 |
|---|---|---|
| `cmd_attack.png` | 공격 | 카이의 증기 대검 — 넓은 강철 날, 놋쇠 가드, 날에 시안색 룬 선, 대각선(오른쪽 위 방향) |
| `cmd_skill.png` | 스킬 | 놋쇠 톱니바퀴 중앙에서 빛나는 시안색 에테르 룬/별, 작은 반짝임 |
| `cmd_talk.png` | 대화(협상) | 놋쇠 테두리 말풍선 안에 빛나는 작은 하트 |
| `cmd_item.png` | 아이템 | 갈색 가죽 가방 + 삐져나온 빛나는 시안 물약병 |
| `cmd_flee.png` | 도주 | 날개 달린 가죽 부츠(놋쇠 버클) + 뒤로 뿜는 증기 |

```
cmd_attack — fantasy steampunk game UI icon of a single broad steam-powered greatsword pointing diagonally to the upper right: wide steel blade with a thin glowing cyan rune line, brass crossguard with a tiny piston, a small puff of white steam at the guard. Single centered object filling about 80% of the canvas, bold chunky silhouette readable at 24 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, soft top-left lighting, no text, no frame, transparent background.
```
```
cmd_skill — fantasy steampunk game UI icon of a polished brass cogwheel with a glowing cyan aether star-rune floating in its center and a few small sparkles. Single centered object filling about 80% of the canvas, bold chunky silhouette readable at 24 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, soft top-left lighting, no text, no frame, transparent background.
```
```
cmd_talk — fantasy steampunk game UI icon of a rounded speech bubble with a riveted brass rim and a cream interior, containing a small glowing rose-gold heart. Single centered object filling about 80% of the canvas, bold chunky silhouette readable at 24 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, soft top-left lighting, no text, no frame, transparent background.
```
```
cmd_item — fantasy steampunk game UI icon of a small brown leather satchel with a brass buckle, a glowing cyan potion flask peeking out of the top. Single centered object filling about 80% of the canvas, bold chunky silhouette readable at 24 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, soft top-left lighting, no text, no frame, transparent background.
```
```
cmd_flee — fantasy steampunk game UI icon of a single winged leather boot with a brass buckle, dashing to the right, a burst of white steam trailing behind it. Single centered object filling about 80% of the canvas, bold chunky silhouette readable at 24 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, soft top-left lighting, no text, no frame, transparent background.
```

### 4-2. 아이템 아이콘 — `item_*.png` (4개)
아이템 메뉴, 일시정지 메뉴의 소지품, 보물상자/전리품 알림, 협상 중 "○○를 내놔" 요구 문구에 쓰입니다. 같은 계열(토닉 → 하이 토닉)은 **한눈에 등급 차이**가 보여야 합니다.

| 파일 | 아이템 | 효과 | 그림 |
|---|---|---|---|
| `item_tonic.png` | 에테르 토닉 | HP 80 회복 | 작고 둥근 유리 플라스크, 코르크 + 놋쇠 목띠, **빛나는 청록 액체**와 작은 기포 |
| `item_hi_tonic.png` | 하이 토닉 | HP 200 회복 | 더 크고 화려한 병을 **놋쇠 세공 케이지**가 감쌈, 더 밝은 에메랄드-시안 액체, 밀랍 봉인 |
| `item_capsule.png` | 증기 캡슐 | AP +3 | **압력 밸브와 작은 압력계가 달린 놋쇠 원통 캡슐**, 이음새의 청백색 빛, 하얀 증기 분출 |
| `item_heart.png` | 태엽 심장 | 전투불능 회복 | **놋쇠·구리 톱니로 만든 기계 심장**, 중심의 따뜻한 붉은 빛, 위에 작은 태엽 열쇠 |

```
item_tonic — fantasy steampunk game UI icon of a small round glass potion flask with a cork stopper and a brass neck band, filled with glowing cyan-teal liquid with tiny bubbles. Single centered object filling about 80% of the canvas, bold chunky silhouette readable at 24 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, soft top-left lighting, no text, no frame, transparent background.
```
```
item_hi_tonic — fantasy steampunk game UI icon of a larger ornate potion bottle encased in an elegant brass filigree cage with a red wax seal, filled with bright glowing emerald-cyan liquid, clearly a premium upgraded version of a basic potion. Single centered object filling about 80% of the canvas, bold chunky silhouette readable at 24 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, soft top-left lighting, no text, no frame, transparent background.
```
```
item_capsule — fantasy steampunk game UI icon of a pressurized brass cylinder capsule with a small valve wheel and a tiny round pressure gauge, glowing blue-white seams, white steam venting from one end. Single centered object filling about 80% of the canvas, bold chunky silhouette readable at 24 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, soft top-left lighting, no text, no frame, transparent background.
```
```
item_heart — fantasy steampunk game UI icon of a mechanical clockwork heart built from brass and copper gears and rivets, a warm glowing red core visible in the center, a small brass wind-up key on top. Single centered object filling about 80% of the canvas, bold chunky silhouette readable at 24 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, soft top-left lighting, no text, no frame, transparent background.
```

### 4-3. 속성 아이콘 — `el_*.png` (5개)
스킬 메뉴의 스킬 이름 앞, 몬스터 도감의 약점/내성 표시에 쓰입니다. 작은 크기에서도 구분되도록 **모두 같은 형태의 원형 메달**(놋쇠 테두리 + 어두운 안쪽 + 속성색 심볼)로 통일합니다. 속성색은 게임 이펙트 색과 같습니다.

| 파일 | 속성 | 심볼 | 색 |
|---|---|---|---|
| `el_phys.png` | 물리 | 검의 베기 궤적 + 충격 별빛 | 크림 화이트 `#fff1d0` |
| `el_fire.png` | 화염 | 양식화된 불꽃 | 주황 `#ff7a2a` |
| `el_frost.png` | 냉기 | 톱니 모양 눈꽃 결정 | 연하늘 `#8fe8ff` |
| `el_volt.png` | 번개 | 구리 코일을 가르는 지그재그 번개 | 노랑 `#fff04a` |
| `el_aether.png` | 에테르 | 궤도 고리를 두른 떠 있는 결정 | 보라 `#c58bff` |

```
el_phys — fantasy steampunk game UI icon: a round medallion with a polished brass rim and a dark inner field, in the center a bold cream-white (#fff1d0) sword slash streak crossing a small impact starburst. Bold chunky symbol readable at 20 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, no text, transparent background.
```
```
el_fire — fantasy steampunk game UI icon: a round medallion with a polished brass rim and a dark inner field, in the center a bold stylized orange (#ff7a2a) flame with a yellow core. Bold chunky symbol readable at 20 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, no text, transparent background.
```
```
el_frost — fantasy steampunk game UI icon: a round medallion with a polished brass rim and a dark inner field, in the center a bold pale icy-blue (#8fe8ff) six-pointed ice crystal shaped like a cogwheel snowflake. Bold chunky symbol readable at 20 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, no text, transparent background.
```
```
el_volt — fantasy steampunk game UI icon: a round medallion with a polished brass rim and a dark inner field, in the center a bold yellow (#fff04a) zigzag lightning bolt striking through a small copper coil. Bold chunky symbol readable at 20 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, no text, transparent background.
```
```
el_aether — fantasy steampunk game UI icon: a round medallion with a polished brass rim and a dark inner field, in the center a bold glowing violet (#c58bff) floating diamond crystal encircled by a thin orbit ring. Bold chunky symbol readable at 20 pixels, hand-painted semi-flat style with cel shading, thick dark-brown outline, no text, transparent background.
```

### 4-4. 상태이상 아이콘 — `st_*.png` (7개)
아군 카드와 적 HP바 아래에 남은 턴 수와 함께 **약 15px**로 표시됩니다. 가장 작으니 **심볼 하나 + 강한 색**이 전부여야 합니다. 속성 아이콘과 같은 원형 메달이지만, **이로운 효과는 시안빛 테두리, 해로운 효과는 붉은빛 테두리**로 구분합니다.

| 파일 | 상태 | 효과 | 심볼 / 색 |
|---|---|---|---|
| `st_atkUp.png` | 공격↑ | 공격력 1.3배 | 칼 + 굵은 위쪽 화살표 / 주홍 |
| `st_defUp.png` | 방어↑ | 받는 피해 감소 | 방패 + 위쪽 화살표 / 파랑 |
| `st_haste.png` | 가속 | 속도 1.5배 | 날개 달린 회중시계 + 속도선 / 초록 |
| `st_guard.png` | 도발 | 적의 공격을 끌어모음 | 한가운데 붉은 과녁이 그려진 단단한 방패 / 금색 |
| `st_burn.png` | 화상 | 턴마다 HP 감소 | 날름거리는 불꽃 / 주황-빨강 |
| `st_atkDown.png` | 공격↓ | 공격력 감소 | 금 간 칼 + 아래쪽 화살표 / 탁한 보라 |
| `st_enraged.png` | 격노 | 협상 실패로 화난 적, 공격력↑ | 만화식 분노 마크(💢) + 김 / 빨강 |

> 파일명 대소문자는 구분하지 않습니다 (`st_atkUp.png` / `st_atkup.png` 모두 인식).

```
st_atkUp — tiny status-effect icon for a fantasy steampunk game: a round medallion with a brass rim glowing soft cyan (beneficial effect), dark inner field, center symbol: a short sword with a bold upward arrow in vivid red-orange. Extremely simple bold shapes readable at 16 pixels, thick dark outline, high contrast, no text, transparent background.
```
```
st_defUp — tiny status-effect icon for a fantasy steampunk game: a round medallion with a brass rim glowing soft cyan (beneficial effect), dark inner field, center symbol: a sturdy round shield with a bold upward arrow in bright blue. Extremely simple bold shapes readable at 16 pixels, thick dark outline, high contrast, no text, transparent background.
```
```
st_haste — tiny status-effect icon for a fantasy steampunk game: a round medallion with a brass rim glowing soft cyan (beneficial effect), dark inner field, center symbol: a winged brass pocket watch with motion speed lines in bright green. Extremely simple bold shapes readable at 16 pixels, thick dark outline, high contrast, no text, transparent background.
```
```
st_guard — tiny status-effect icon for a fantasy steampunk game: a round medallion with a brass rim glowing soft cyan (beneficial effect), dark inner field, center symbol: a heavy golden shield with a red bullseye target painted on it, meaning it draws enemy attacks. Extremely simple bold shapes readable at 16 pixels, thick dark outline, high contrast, no text, transparent background.
```
```
st_burn — tiny status-effect icon for a fantasy steampunk game: a round medallion with a brass rim glowing red (harmful effect), dark inner field, center symbol: a licking flame in orange-red with a yellow core. Extremely simple bold shapes readable at 16 pixels, thick dark outline, high contrast, no text, transparent background.
```
```
st_atkDown — tiny status-effect icon for a fantasy steampunk game: a round medallion with a brass rim glowing red (harmful effect), dark inner field, center symbol: a cracked short sword with a bold downward arrow in dull purple. Extremely simple bold shapes readable at 16 pixels, thick dark outline, high contrast, no text, transparent background.
```
```
st_enraged — tiny status-effect icon for a fantasy steampunk game: a round medallion with a brass rim glowing red (harmful effect), dark inner field, center symbol: a bold red manga-style anger vein mark (cross-shaped popping vein symbol) with a small puff of steam. Extremely simple bold shapes readable at 16 pixels, thick dark outline, high contrast, no text, transparent background.
```

---

## 5. 시스템 아이콘 (★3) — `portraits/system.png`

협상 중 「시스템」이 성격 안내나 협상 불가 안내를 할 때 대화창 왼쪽(84px)에 뜨는 그림입니다. 게임의 안내자 같은 느낌.
- **놋쇠 톱니바퀴 엠블럼 중앙에 빛나는 시안색 에테르 눈**, 주위로 은은한 빛.

```
Emblem portrait for a fantasy steampunk JRPG system narrator: a polished brass cogwheel emblem with a single glowing cyan aether eye in its center, faint rays of cyan light and a few floating sparkles, mysterious and helpful mood. Centered with comfortable margin so it survives a circular crop. Hand-painted semi-flat style with cel shading, thick dark-brown outline, no text, transparent background (if unavailable: flat solid #3a3020 background).
```

---

## 6. 협상 표정 변형 (★3) — `portraits/<몬스터>_happy.png`, `_angry.png`

여신전생식 협상에서 **좋아하는 대답을 하면 happy, 싫어하는 대답·거절·격노 시 angry** 초상화로 바뀝니다. 파일이 없으면 기본 초상화를 씁니다.
대상: `cograt`, `slime`, `wisp`, `beetle`, `knight`, `golem` × 2 = **12장**.

**만드는 법:** 새로 생성하지 말고, 완성된 기본 초상화를 첨부한 뒤 아래 편집 문장을 사용하세요. (GPT 이미지 편집, Gemini/Nano Banana, Midjourney Vary Region/Editor, SD img2img denoise 0.35~0.5)

```
Edit the attached portrait: keep the exact same character design, colors, framing, art style and transparent background. Change only the expression and small effects as follows: <아래 표의 문장>
```

| 몬스터 | happy (`_happy.png`) | angry (`_angry.png`) |
|---|---|---|
| 톱니쥐 | `ears perked up, eyes curved into happy crescents with a soft red glow, tiny sparkles around its head, relieved little smile` | `ears pinned back, red eyes flaring brightly, brass gear-teeth bared, tail bristling, puffs of steam from its joints` |
| 보일러 젤리 | `gauge needles swung happily to the top, jelly bouncing with little heart-shaped steam puffs from the valve` | `gauge needles slammed into the red danger zone, valve blasting steam, jelly bubbling and tinted slightly red` |
| 램프 위스프 | `flame burning tall and bright with cheerful closed smiling eyes, warm golden sparkles` | `flame flaring wildly in red-orange with narrowed angry eyes, sparks bursting out of the lantern` |
| 놋쇠 딱정벌레 | `smug satisfied look, chin raised higher, a big gleaming sparkle on its polished shell` | `horn lowered to charge, green eyes blazing, steam hissing from its joints, legs braced` |
| 태엽 기사 | `visor glow softened to a warm gentle amber, slight approving nod, one gauntlet placed over its chest` | `visor slit blazing orange-red, halberd raised menacingly, steam venting from the armor seams` |
| 증기 골렘 | `furnace glowing a warm contented orange, a satisfied puff of white smoke from the chimney` | `furnace roaring with fire spilling out of the grille, thick black smoke billowing from the chimney, visor glowing red` |

---

## 7. 전투 UI 에셋 (UI 바이블 기반) — `ui/*`, `portraits/cutin_*`

전투 화면은 [UI 바이블](ui/UI_BIBLE.md)에 따라 다시 만들었습니다. 이 절의 그림이 없으면 CSS/SVG 대체물이 보이고, 파일을 넣으면 그 자리를 바로 대신합니다.

### 7-0. 이 절의 공통 규칙 (§1과 다른 점)
- **색은 딱 두 가지: 먹색(`#0b0907`) + 황금(`#d4a83a` ~ `#f2c94c`).** §1의 시안·보라 마법광은 UI 프레임에 쓰지 않습니다. 진홍(`#c8283a`)은 적·위험 표시에만 씁니다.
- **재질 언어:** 상시 UI는 정밀한 **황동 기계**(톱니, 눈금, 리벳), 순간 연출은 깃펜의 **잉크**(날카로운 붓 획, 튀는 방울)입니다. 한 그림에 두 언어를 섞지 마세요.
- **글자 금지.** 모든 글자는 게임이 서체로 따로 그립니다.
- **배경 투명 필수.** 잉크류는 "검은 잉크, 흰 배경"으로 만든 뒤 흰색을 투명으로 바꾸는 게 가장 깔끔합니다(포토샵: *색상 범위 → 흰색 삭제*, 또는 `Multiply` 상태로 알파 추출).
- **기울기:** 화면의 기본 사선은 오른쪽 위로 6° 정도 올라가는 각도입니다. 그림 자체를 기울이지 않아도 게임이 돌려 놓으니 **수평·정면으로** 그려 주세요(컷인 초상만 예외).

### 7-1. 컷인 상반신 (★1) — `portraits/cutin_kai.png`, `cutin_lyra.png`
**어디에:** 스킬을 쓰거나 전원 패링 반격(COUNTER)이 나올 때, 화면을 가로지르는 먹색 띠 왼쪽에 0.6초 동안 미끄러져 들어오는 사선(평행사변형) 창.
**구도:** 허리 위 상반신, 액션 포즈, **몸과 시선이 화면 오른쪽(기술명 방향)을 향함.** 창이 좌우로 22%씩 비스듬히 잘리니 얼굴과 손은 가운데 60% 안에 두세요. 기존 초상화를 *캐릭터 레퍼런스*로 첨부하면 일치도가 올라갑니다.
**생성/저장:** 1024×1024 생성 → 512×512 저장, 투명 배경.

카이:
```
Dynamic waist-up action shot for a JRPG skill cut-in. Kai, the 18-year-old steam swordsman (match the attached character reference exactly: messy spiky dark-brown hair, brass aviator goggles on the forehead, deep navy long coat with brass epaulettes, red scarf, brass steam backpack). He swings a broad steam-powered sword toward the right with both hands, the blade vents a sharp jet of white steam, his scarf whips behind him, fierce focused eyes looking to the right. Strong diagonal composition rising to the upper right, face and hands kept in the central 60% of the frame. Anime JRPG illustration, bold cel shading, high contrast, warm gold key light from the upper left, deep black shadows. Isolated on a transparent background, no effects outside the character silhouette, no text, no frame.
```
리라:
```
Dynamic waist-up action shot for a JRPG skill cut-in. Lyra, the aether mage (match the attached character reference exactly). She thrusts her brass-and-crystal staff toward the right, her other hand open with a small burst of golden runes, hat brim and long hair swept back by the spell's wind, calm but intense eyes looking to the right. Strong diagonal composition rising to the upper right, face and hands kept in the central 60% of the frame. Anime JRPG illustration, bold cel shading, high contrast, warm gold key light from the upper left, deep black shadows. Isolated on a transparent background, no text, no frame.
```
몬스터(★3, `cutin_cograt.png` 등 6종 — 영입 후 스킬 컷인용, 없으면 일반 초상으로 대체): 위 문장의 인물 설명을 §3의 해당 몬스터 설명으로 바꾸고 "attacking toward the right"로 쓰면 됩니다.

### 7-2. 톱니 링 (★1) — `ui/gear_ring.png`
**어디에:** 아군 차례에 캐릭터 옆에 뜨는 커맨드 링의 본체. 명령을 고를 때마다 **한 칸씩 회전**하고, 가운데 구멍 위에 게임이 AP 숫자와 눈금을 그립니다.
**주의:** 회전하므로 **빛 방향이 드러나지 않게**(고른 조명, 하이라이트는 원을 따라 균일하게). 정확히 원형·정중앙, **가운데 지름의 약 58%는 투명한 구멍**. 이빨은 12~16개.
**생성/저장:** 1024×1024 생성 → 512×512 저장.
```
A single ornate brass cogwheel ring seen perfectly flat from the front, for a game UI, isolated on a transparent background. Exactly circular and centered, 14 evenly spaced sharp teeth around the outside, a wide empty circular hole in the middle about 58% of the diameter (fully transparent). Engraved fine clock-dial tick marks running around the inner rim, a few rivets, subtle filigree etching. Polished warm brass and gold (#d4a83a to #f2c94c) with a thin dark ink-black outline, even soft lighting with no directional shadow so it can rotate freely, crisp clean edges, high contrast. Flat orthographic view, no perspective, no text, no background.
```

### 7-3. 컷인 잉크 띠 (★2) — `ui/ink_band.png`
**어디에:** 컷인 때 화면을 가로로 가르는 먹색 띠(초상과 기술명이 그 위에 얹힘). 띠 가운데는 글자가 올라가니 **안쪽은 꽉 찬 먹색**, 위아래 가장자리만 붓결과 튄 방울.
**생성/저장:** 가로 2400×360 정도(16:2.4)로 생성 → 그대로 저장. 흰 배경 검은 잉크로 만든 뒤 흰색 제거.
```
One single long horizontal brush stroke of thick black sumi ink, painted left to right with a wide flat brush across the entire width, very wide format 2400x360. The center of the stroke is solid opaque black; the top and bottom edges are rough and dry-brushed with bristle streaks, the right end tapers into a sharp splatter, a few small ink droplets flung above and below. Pure black ink on a plain white background, high contrast, no grey wash, no text, no other objects.
```

### 7-4. 잉크 얼룩 (★2) — `ui/ink_splat.png`
**어디에:** PARRY! · WEAK · BREAK 같은 순간 문구 뒤에 깔리는 얼룩. 금색 글자가 그 위에 올라갑니다.
**구도:** 가로로 긴 타원형 덩어리(가로:세로 ≈ 2.2:1), 가장자리에 튄 방울 몇 개. 가운데는 꽉 찬 먹색.
**생성/저장:** 1024×512 → 512×256 저장, 흰색 제거해 투명.
```
A single splash of thick black ink hitting paper, horizontally elongated blot about 2.2 times wider than tall, solid opaque black center with an irregular splashed outline, a handful of small round droplets and thin spatter streaks flying out to the left and right. Pure black on plain white background, high contrast, no grey, no text, centered, wide format 2:1.
```

### 7-5. 대상 칼날 표식 (★2) — `ui/target_blade.png`
**어디에:** 공격 대상을 고를 때 선택된 적 머리 위에 꽂히는 작은 단검. 게임이 14° 기울여 그립니다.
**구도:** **세로로 곧게, 칼끝이 아래**. 짧은 십자 손잡이, 황금 칼날, 두꺼운 먹색 외곽선. 26×54px로 줄어도 형태가 보이게 단순하게.
**생성/저장:** 512×1024 생성 → 128×256 저장, 투명.
```
A small stylized dagger icon for a game target marker, pointing straight down, vertical and centered, simple bold silhouette: short cross-shaped brass hilt at the top, a sharp polished gold blade (#f2c94c) tapering to a point at the bottom, a thick black ink outline around everything, a single crisp highlight line down the blade. Flat game UI icon style, high contrast, readable when shrunk to 26x54 pixels, transparent background, no text, no shadow.
```

### 7-6. 잉크 결 텍스처 (★3) — `ui/ink_texture.png`
**어디에:** 커맨드 칼날, 파티 카드, 설명 띠 같은 **모든 먹색 패널**의 바탕에 반복해서 깔립니다. 거의 검은색이어야 글자가 읽힙니다.
**주의:** **이음매 없는(seamless) 타일.** 밝기 차이는 아주 작게(검정 `#0b0907` ~ 짙은 갈색 `#1c160f` 사이).
**생성/저장:** 1024×1024 → 256×256 저장, 불투명.
```
Seamless tileable texture of dried black sumi ink on handmade paper, very dark (between #0b0907 and #1c160f), subtle brush streaks and fine paper fibre grain, very low contrast so text on top stays readable, no visible seams, no spots brighter than dark brown, flat lighting, square 1:1, no text, no objects.
```

### 7-7. 여신의 깃털 (★2) — `ui/feather.png`
**어디에:** 협상에서 영입에 성공했을 때 화면 위에서 십여 장이 흔들리며 떨어집니다. 바이블의 세 번째 재질 언어(**깃털 = 여신의 은총**)이고, 드물게만 나옵니다.
**구도:** 깃털 한 장, **세로로 곧게 깃대가 아래**, 가늘고 긴 비율(1:3). 흰색~크림색 깃털에 가장자리만 은은한 금빛. 게임이 회전·크기를 바꾸므로 그림 자체는 정면·수평.
**생성/저장:** 512×1536 생성 → 128×384 저장, 투명.
```
A single elegant white feather of a goddess, standing vertically with the quill at the bottom, slender 1:3 proportion, soft cream-white vanes with delicate barbs, the edges and the shaft touched with a faint warm gold glow (#f2c94c), a few barbs gently separated at the tip. Soft painterly anime illustration, clean silhouette, isolated on a transparent background, no text, no other objects.
```

---

## 8. 후처리 & 적용 체크리스트

1. **배경 제거** (투명으로 못 뽑았을 때): Photoshop *배경 제거*, remove.bg, `rembg` 등.
2. **여백 정리 & 리사이즈**: 초상화 512×512 / 아이콘 256×256 / 로고 가로 ≤1600. 축소는 *Lanczos/Bicubic Sharper* 권장.
3. **축소 테스트**: 아이콘은 24px, 상태 아이콘은 16px로 줄여 보고 무엇인지 구분되는지 확인.
4. **저장**: 아래 경로/이름 그대로 저장하면 `npm run dev` 화면이 자동 새로고침되며 즉시 반영됩니다.

```
public/art/ui/logo.png
public/art/portraits/kai.png        lyra.png      cograt.png    slime.png
public/art/portraits/wisp.png       beetle.png    knight.png    golem.png
public/art/portraits/system.png
public/art/portraits/cograt_happy.png  cograt_angry.png   slime_happy.png   slime_angry.png
public/art/portraits/wisp_happy.png    wisp_angry.png     beetle_happy.png  beetle_angry.png
public/art/portraits/knight_happy.png  knight_angry.png   golem_happy.png   golem_angry.png
public/art/icons/cmd_attack.png  cmd_skill.png  cmd_talk.png  cmd_item.png  cmd_flee.png
public/art/icons/item_tonic.png  item_hi_tonic.png  item_capsule.png  item_heart.png
public/art/icons/el_phys.png  el_fire.png  el_frost.png  el_volt.png  el_aether.png
public/art/icons/st_atkUp.png  st_defUp.png  st_haste.png  st_guard.png  st_burn.png  st_atkDown.png  st_enraged.png
public/art/portraits/cutin_kai.png  cutin_lyra.png   (cutin_<몬스터>.png 선택)
public/art/ui/gear_ring.png  ink_band.png  ink_splat.png  target_blade.png  ink_texture.png  feather.png
```

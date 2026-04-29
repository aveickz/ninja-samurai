// Допустимые типы: weapon | trap | character | modifier | defense | stance | effect | intervention | group | action
const CARDS = [

  // ── ОРУЖИЕ (стр. 1–5) ────────────────────────────────────────────
  {
    id: 1,
    title: "Катана",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 2.",
    img: "cards/01_geysha.jpg"
  },
  {
    id: 2,
    title: "Сюко",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 1.",
    img: "cards/01_geysha.jpg"
  },
  {
    id: 3,
    title: "Канабо",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 3. Атакуемый игрок скидывает случайную карту в случае успешной атаки.",
    img: "cards/01_geysha.jpg"
  },
  {
    id: 4,
    title: "Боккэн",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 0. Вы берёте карту из колоды в случае успешной атаки.",
    img: "cards/01_geysha.jpg"
  },
  {
    id: 5,
    title: "Кинжал предателя",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 2, сила 1. Нельзя защититься. Игнорирует ловушки. Можно производить атаку будучи в дуэли. Нельзя атаковать Сёгуна.",
    img: "cards/01_geysha.jpg"
  },
  {
    id: 6,
    title: "Боевой веер",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 2, сила 1. Можно воспользоваться либо как обычным оружием 1/2, либо как метательным оружием 3/1.",
    img: "cards/01_geysha.jpg"
  },
  {
    id: 7,
    title: "Кусаригама",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 2, сила 2.",
    img: "cards/01_geysha.jpg"
  },
  {
    id: 8,
    title: "Вакидзаси",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 2.",
    img: "cards/01_geysha.jpg"
  },
  {
    id: 9,
    title: "Шипастый щит",
    types: ["weapon", "defense"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 1. Можно использовать как карту Защиты.",
    img: "cards/01_geysha.jpg"
  },
  {
    id: 10,
    title: "Тонфа",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 1. Атакуемый игрок скидывает случайную карту в случае успешной атаки.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 11,
    title: "Кама",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 3.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 12,
    title: "Меч сёгуна",
    types: ["weapon"],
    qty: 3,
    group: "weapon",
    desc: "Дальность 3, сила 3. Только Сёгун может проводить прямую атаку этим оружием. Можно сыграть как вмешательство, чтобы передать эту карту Сёгуну в обмен на другую в закрытую.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 13,
    title: "Тэккокаги",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 4.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 14,
    title: "Нунчаки",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 2.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 15,
    title: "Танто",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 2.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 16,
    title: "Тэкко",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 3.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 17,
    title: "МаКадо",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 1.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 18,
    title: "Сай",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 2.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 19,
    title: "Явара",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 1. Атакуемый игрок скидывает случайную карту в случае успешной атаки.",
    img: "cards/03_vyzhivshiy.jpg"
  },
  {
    id: 20,
    title: "Отравленный боевой веер",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 2, сила 1. Можно воспользоваться либо как обычным оружием 1/2, либо как метательным оружием 3/1.",
    img: "cards/03_vyzhivshiy.jpg"
  },
  {
    id: 21,
    title: "Отравленный сай",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 3, сила 1. Можно воспользоваться либо как обычным оружием 1/2, либо как метательным оружием 3/1.",
    img: "cards/03_vyzhivshiy.jpg"
  },
  {
    id: 22,
    title: "Дзюттэ",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 1.",
    img: "cards/03_vyzhivshiy.jpg"
  },
  {
    id: 23,
    title: "Нунти",
    types: ["weapon"],
    qty: 1,
    group: "weapon",
    desc: "Дальность 1, сила 2.",
    img: "cards/03_vyzhivshiy.jpg"
  },
  {
    id: 24,
    title: "Бо",
    types: ["weapon"],
    qty: 2,
    group: "weapon",
    desc: "Дальность 2, сила 1. Атакуемый игрок теряет стойку в случае успешной атаки.",
    img: "cards/04_makibishi.jpg"
  },
  {
    id: 25,
    title: "Нодати",
    types: ["weapon"],
    qty: 2,
    group: "weapon",
    desc: "Дальность 2, сила 3. Атакуемый игрок теряет стойку в случае успешной атаки.",
    img: "cards/04_makibishi.jpg"
  },
  {
    id: 26,
    title: "Кёкэцусёгэ",
    types: ["weapon"],
    qty: 2,
    group: "weapon",
    desc: "Дальность 2, сила 2. В случае успешной атаки вы забираете карту из руки врага.",
    img: "cards/04_makibishi.jpg"
  },
  {
    id: 27,
    title: "Манрики",
    types: ["weapon"],
    qty: 2,
    group: "weapon",
    desc: "Дальность 2, сила 1. В случае успешной атаки вы забираете карту из руки врага.",
    img: "cards/04_makibishi.jpg"
  },
  {
    id: 28,
    title: "Нагината",
    types: ["weapon"],
    qty: 2,
    group: "weapon",
    desc: "Дальность >1, сила 2. Может ударить на любом расстоянии более двух.",
    img: "cards/04_makibishi.jpg"
  },
  {
    id: 29,
    title: "Яри",
    types: ["weapon"],
    qty: 2,
    group: "weapon",
    desc: "Дальность 2, сила 1.",
    img: "cards/04_makibishi.jpg"
  },
  {
    id: 30,
    title: "Камаяри",
    types: ["weapon"],
    qty: 2,
    group: "weapon",
    desc: "Дальность 2, сила 1.",
    img: "cards/04_makibishi.jpg"
  },
  {
    id: 31,
    title: "Отравленный яри",
    types: ["weapon"],
    qty: 2,
    group: "weapon",
    desc: "Дальность 2, сила 2.",
    img: "cards/04_makibishi.jpg"
  },
  {
    id: 32,
    title: "Сюрикен",
    types: ["weapon"],
    qty: 3,
    group: "weapon",
    desc: "Дальность >1, сила 1.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 33,
    title: "Дайкю",
    types: ["weapon"],
    qty: 3,
    group: "weapon",
    desc: "Дальность 3, сила 2.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 34,
    title: "Отравленный сюрикен",
    types: ["weapon"],
    qty: 3,
    group: "weapon",
    desc: "Дальность 3, сила 1.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 35,
    title: "Кунай",
    types: ["weapon"],
    qty: 3,
    group: "weapon",
    desc: "Дальность >1, сила 2.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 36,
    title: "Бумеранг",
    types: ["weapon"],
    qty: 3,
    group: "weapon",
    desc: "Дальность 3, сила 1. В случае успешной атаки это оружие возвращается вам в руку.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 37,
    title: "Отравленный дайкю",
    types: ["weapon"],
    qty: 3,
    group: "weapon",
    desc: "Дальность 3, сила 1.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 38,
    title: "Макибиши",
    types: ["weapon", "trap"],
    qty: 3,
    group: "weapon",
    desc: "Дальность 3, сила 0. Можно использовать как ловушку, которая наносит одну рану атакующему в ответ.",
    img: "cards/04_makibishi.jpg"
  },
  {
    id: 39,
    title: "Дротик с ядом",
    types: ["weapon"],
    qty: 3,
    group: "weapon",
    desc: "Дальность 3, сила 1. Атака игнорирует ловушки и защиту, и вы берёте карту из колоды.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 40,
    title: "Отравленный кунай",
    types: ["weapon"],
    qty: 3,
    group: "weapon",
    desc: "Дальность >1, сила 1.",
    img: "cards/05_vmeshatelstvo.jpg"
  },

  // ── ЛОВУШКИ (стр. 7) ─────────────────────────────────────────────
  {
    id: 41,
    title: "Силок",
    types: ["trap"],
    qty: 1,
    group: "trap",
    desc: "ЛОВУШКА. Вы забираете у атакующего две карты.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 42,
    title: "Чучело",
    types: ["trap"],
    qty: 1,
    group: "trap",
    desc: "ЛОВУШКА. Атака не проходит.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 43,
    title: "Капкан",
    types: ["trap"],
    qty: 1,
    group: "trap",
    desc: "ЛОВУШКА. Атакующий получает две раны от владельца ловушки.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 44,
    title: "Рикошет",
    types: ["trap"],
    qty: 1,
    group: "trap",
    desc: "ЛОВУШКА. Изначальная атака не проходит и обращается обратно, равная силе оружия. Атакующий может защититься от рикошета.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 45,
    title: "Поганка",
    types: ["trap"],
    qty: 1,
    group: "trap",
    desc: "ЛОВУШКА. Враг отравляется ядом. Если он уже отравлен, то получает 1 рану.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 46,
    title: "Боевой банан",
    types: ["trap"],
    qty: 1,
    group: "trap",
    desc: "ЛОВУШКА. Атакующий теряет свою стойку и сбрасывает две карты с руки на ваш выбор.",
    img: "cards/02_tenevoy_pakt.jpg"
  },
  {
    id: 47,
    title: "Оскорбление",
    types: ["trap"],
    qty: 1,
    group: "trap",
    desc: "Ловушка. Вы оскорбляете атакующего.",
    img: "cards/02_tenevoy_pakt.jpg"
  },

  // ── ЗАЩИТА (стр. 8) ──────────────────────────────────────────────
  {
    id: 48,
    title: "Защита",
    types: ["defense"],
    qty: 1,
    group: "defense",
    desc: "ЗАЩИТА ~ Атакующий получает одну рану от вас.",
    img: "cards/11_besstrasie.jpg"
  },
  {
    id: 49,
    title: "Скрытый кинжал",
    types: ["defense"],
    qty: 1,
    group: "defense",
    desc: "ЗАЩИТА ~ Атакующий получает одну рану от вас.",
    img: "cards/11_besstrasie.jpg"
  },
  {
    id: 50,
    title: "Ядовитые наручи",
    types: ["defense"],
    qty: 1,
    group: "defense",
    desc: "ЗАЩИТА ~ Атакующий получает отравление ядом.",
    img: "cards/11_besstrasie.jpg"
  },
  {
    id: 51,
    title: "Идеальный момент",
    types: ["defense"],
    qty: 1,
    group: "defense",
    desc: "ЗАЩИТА ~ Вы забираете у атакующего случайную карту.",
    img: "cards/11_besstrasie.jpg"
  },
  {
    id: 52,
    title: "Выдержка самурая",
    types: ["defense"],
    qty: 1,
    group: "defense",
    desc: "ЗАЩИТА ~ Вы также берёте карту из колоды.",
    img: "cards/11_besstrasie.jpg"
  },
  {
    id: 53,
    title: "Карманник",
    types: ["defense"],
    qty: 1,
    group: "defense",
    desc: "ЗАЩИТА ~ Вы можете выбрать сколько ран вы хотите получить при атаке, и за каждую рану берёте карту из колоды.",
    img: "cards/11_besstrasie.jpg"
  },
  {
    id: 54,
    title: "Ошеломление",
    types: ["defense"],
    qty: 1,
    group: "defense",
    desc: "ЗАЩИТА ~ Атакующий сбрасывает случайную карту.",
    img: "cards/11_besstrasie.jpg"
  },
  {
    id: 55,
    title: "Захват",
    types: ["defense"],
    qty: 1,
    group: "defense",
    desc: "ЗАЩИТА ~ Вы забираете не метательное оружие врага себе в руку.",
    img: "cards/11_besstrasie.jpg"
  },
  {
    id: 56,
    title: "Блок",
    types: ["defense", "intervention"],
    qty: 1,
    group: "defense",
    desc: "ВМЕШАТЕЛЬСТВО~ЗАЩИТА. Можно сыграть в любой момент за любого игрока.",
    img: "cards/11_besstrasie.jpg"
  },

  // ── СТОЙКИ (стр. 9) ──────────────────────────────────────────────
  {
    id: 57,
    title: "Тень",
    types: ["stance"],
    qty: 1,
    group: "stance",
    desc: "СТОЙКА ~ Вы обескровлены для других игроков весь раунд, но в начале своего хода вы сбрасываете эту стойку.",
    img: "cards/03_vyzhivshiy.jpg"
  },
  {
    id: 58,
    title: "Всадник",
    types: ["stance"],
    qty: 1,
    group: "stance",
    desc: "СТОЙКА ~ Вы находитесь дальше от всех на единицу при атаках по вам. Ваши атаки могут достать дальше на один.",
    img: "cards/03_vyzhivshiy.jpg"
  },
  {
    id: 59,
    title: "Лотос",
    types: ["stance"],
    qty: 1,
    group: "stance",
    desc: "СТОЙКА ~ При выставлении восстановить два жетона стойкости и перед каждой фазой набора вы можете: восстановить жетон стойкости любому игроку ИЛИ снять яд или один эффект любому игроку, сбросив карту.",
    img: "cards/03_vyzhivshiy.jpg"
  },
  {
    id: 60,
    title: "Щитоносец",
    types: ["stance"],
    qty: 1,
    group: "stance",
    desc: "СТОЙКА ~ Каждый раз при прямой атаке по вам снижаете урон на один. Дополнительно можете скинуть карту с руки за каждое снижение урона (не менее одного).",
    img: "cards/03_vyzhivshiy.jpg"
  },
  {
    id: 61,
    title: "Мастер боя",
    types: ["stance"],
    qty: 1,
    group: "stance",
    desc: "СТОЙКА ~ Каждый раз нанести врагу на одну рану больше по врагу взять одну карту из колоды после атаки вы можете: взять карту из колоды.",
    img: "cards/03_vyzhivshiy.jpg"
  },
  {
    id: 62,
    title: "Капеллан",
    types: ["stance"],
    qty: 1,
    group: "stance",
    desc: "СТОЙКА ~ Раз в свой ход вы можете: восстановить жетон стойкости любому игроку ИЛИ снять яд или один эффект любому игроку, сбросив карту.",
    img: "cards/03_vyzhivshiy.jpg"
  },
  {
    id: 63,
    title: "Ассасин",
    types: ["stance"],
    qty: 1,
    group: "stance",
    desc: "СТОЙКА ~ При атаке по врагу вы можете: сделать вашу атаку отравленной ядом ИЛИ сбросив две карты, сделать врага беззащитным от атаки.",
    img: "cards/03_vyzhivshiy.jpg"
  },

  // ── МОДИФИКАТОРЫ (стр. 10–11) ─────────────────────────────────────
  {
    id: 64,
    title: "Флакон яда",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Ваша атака теперь накладывает отравление.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 65,
    title: "Точило",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Ваша атака наносит на одну рану больше.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 66,
    title: "Инь и Ян",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Дальность и сила атаки меняются местами.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 67,
    title: "Удар тени",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Ваша атака игнорирует ловушки.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 68,
    title: "Выпад",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Дальность вашей атаки увеличивается на единицу.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 69,
    title: "Поступь ветра",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ От вашей атаки невозможно защититься, однако ловушки продолжают действовать.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 70,
    title: "Гнев сёгуна",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Атаку можно провести даже по обескровленному игроку. Сёгун наносит на одну рану больше.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 71,
    title: "Целебный клинок",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ В случае успешной атаки вы восстанавливаете себе столько жетонов здоровья, сколько нанесли ран.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 72,
    title: "Порыв ярости",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Атака наносит удар по двум целям одновременно. Однако сила и дальность снижаются на один.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 73,
    title: "Повязка камикадзе",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Ваша атака может бить на любом расстоянии и вы наносите на одну рану больше, но вы теряете один жетон стойкости. Нельзя применить на пороге смерти.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 74,
    title: "Сокрушительный бросок",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Увеличивает дальность атаки на два, но сила атаки (не оружия) становится равна единице. Делает атаку метательной.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 75,
    title: "Удар камикадзе",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Итоговая сила атаки становится равна вашему количеству жетонов здоровья.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 76,
    title: "Кипящий яд",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Отравленный противник получит на две раны больше.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 77,
    title: "Длань сёгуна",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Вы не тратите свою попытку атаки в данном ударе.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 78,
    title: "Дух сёгуна",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ От вашей атаки невозможно защититься, и ловушки не действуют.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 79,
    title: "Пронзительный удар",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Ваша атака оружием полностью игнорирует все бонусы от стойки и персонажа врага.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 80,
    title: "Критический удар",
    types: ["modifier"],
    qty: 1,
    group: "modifier",
    desc: "МОДИФИКАТОР ~ Ваша базовая сила атаки оружием удваивается.",
    img: "cards/09_plagiat.jpg"
  },

  // ── ГРУППОВЫЕ ДЕЙСТВИЯ (стр. 12) ─────────────────────────────────
  {
    id: 81,
    title: "Целительные источники",
    types: ["group", "action"],
    qty: 1,
    group: "group",
    desc: "Восстановите два жетона стойкости, а все остальные активные игроки один.",
    img: "cards/08_obrok.jpg"
  },
  {
    id: 82,
    title: "Миротворцы",
    types: ["group", "action"],
    qty: 1,
    group: "group",
    desc: "Остальные активные игроки скидывают карту защиты или оружия, либо отдают вам карту из руки на свой выбор.",
    img: "cards/08_obrok.jpg"
  },
  {
    id: 83,
    title: "Потасовка",
    types: ["group", "action"],
    qty: 1,
    group: "group",
    desc: "Все активные игроки теряют стойку. Сёгун не участвует в потасовке.",
    img: "cards/08_obrok.jpg"
  },
  {
    id: 84,
    title: "Чайная церемония",
    types: ["group", "action"],
    qty: 1,
    group: "group",
    desc: "Вы берёте три карты, остальные активные игроки берут по одной.",
    img: "cards/08_obrok.jpg"
  },
  {
    id: 85,
    title: "Просветление",
    types: ["group", "action"],
    qty: 1,
    group: "group",
    desc: "Все ловушки на столе открываются, но продолжают действовать.",
    img: "cards/08_obrok.jpg"
  },
  {
    id: 86,
    title: "Вихрь ярости",
    types: ["group", "action"],
    qty: 1,
    group: "group",
    desc: "Играется в паре с картой не метательного оружия с дальностью более одного. Минуя ловушки, активные игроки получают урон от оружия (без бонусов) или скидывают защиту. Тратит атаку.",
    img: "cards/08_obrok.jpg"
  },
  {
    id: 87,
    title: "Шквал огня",
    types: ["group", "action"],
    qty: 1,
    group: "group",
    desc: "Играется в паре с картой метательного оружия. Минуя ловушки, активные игроки получают две раны или скидывают защиту. Тратит атаку.",
    img: "cards/08_obrok.jpg"
  },
  {
    id: 88,
    title: "Бочка зловония",
    types: ["group", "effect"],
    qty: 2,
    group: "group",
    desc: "Все активные игроки получают отравление ядом.",
    img: "cards/13_bochka_zlovoniya.jpg"
  },
  {
    id: 89,
    title: "Град стрел",
    types: ["group", "action"],
    qty: 1,
    group: "group",
    desc: "Остальные активные игроки скидывают карту оружия или жетон стойкости.",
    img: "cards/08_obrok.jpg"
  },
  {
    id: 90,
    title: "Боевой крик",
    types: ["group", "action"],
    qty: 1,
    group: "group",
    desc: "Все ловушки на столе сбрасываются в сброс.",
    img: "cards/08_obrok.jpg"
  },

  // ── ЭФФЕКТЫ постоянные/разовые (стр. 13–14) ──────────────────────
  {
    id: 91,
    title: "Метка убийцы",
    types: ["effect"],
    qty: 1,
    group: "effect",
    desc: "ПОСТОЯННЫЙ эффект. Все атаки по вам наносят на одну рану больше.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 92,
    title: "Противоядие",
    types: ["effect"],
    qty: 1,
    group: "effect",
    desc: "ПОСТОЯННЫЙ эффект. Вас нельзя отравить ядом. Текущее отравление снимается.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 93,
    title: "Укус змеи",
    types: ["effect"],
    qty: 1,
    group: "effect",
    desc: "ПОСТОЯННЫЙ эффект. Каждое лечение по игроку снижается на единицу. Также все негативные эффекты от отравления удваиваются.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 94,
    title: "Кагинава",
    types: ["effect"],
    qty: 1,
    group: "effect",
    desc: "ПОСТОЯННЫЙ эффект. Атаки по вам могут быть произведены без ограничения дальности.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 95,
    title: "Разоружение",
    types: ["effect"],
    qty: 1,
    group: "effect",
    desc: "ПОСТОЯННЫЙ эффект. Выбранный игрок не может производить прямые атаки оружием.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 96,
    title: "Завеса дыма",
    types: ["effect"],
    qty: 1,
    group: "effect",
    desc: "РАЗОВЫЙ эффект. Следующий игровой ход выбранный игрок будто обескровлен.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 97,
    title: "Пыль в глаза",
    types: ["effect"],
    qty: 1,
    group: "effect",
    desc: "ПОСТОЯННЫЙ эффект. Атаки игрока не может бить дальше расстояния в единицу.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 98,
    title: "Палочка благовоний",
    types: ["effect", "action"],
    qty: 2,
    group: "effect",
    desc: "Выбранный игрок скидывает один выбранный вами эффект. Вы можете восстановить жизнь или взять карту из колоды.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 99,
    title: "Чаша благовоний",
    types: ["effect", "action"],
    qty: 1,
    group: "effect",
    desc: "Выбранный игрок скидывает все эффекты. За каждый сброшенный эффект вы можете восстановить жизнь или взять карту из колоды.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 100,
    title: "Слабость",
    types: ["effect"],
    qty: 1,
    group: "effect",
    desc: "ПОСТОЯННЫЙ эффект. Следующая атака не может нанести более одной раны.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 101,
    title: "Беззащитность",
    types: ["effect"],
    qty: 1,
    group: "effect",
    desc: "ПОСТОЯННЫЙ эффект. Игрок не может защищаться от атак.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 102,
    title: "Дух лидера",
    types: ["effect"],
    qty: 1,
    group: "effect",
    desc: "ПОСТОЯННЫЙ эффект. Выбранный игрок наносит на одну рану больше.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 103,
    title: "Бессилие",
    types: ["effect"],
    qty: 1,
    group: "effect",
    desc: "ПОСТОЯННЫЙ эффект. За ход вы можете сделать на одну прямую атаку меньше.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },
  {
    id: 104,
    title: "Эгида",
    types: ["effect"],
    qty: 1,
    group: "effect",
    desc: "РАЗОВЫЙ эффект. Выбранный игрок автоматически защищается от атаки.",
    img: "cards/16_palochka_blagovoniy.jpg"
  },

  // ── ДЕЙСТВИЯ (стр. 15–16) ─────────────────────────────────────────
  {
    id: 105,
    title: "Васаби",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Выбранный игрок избавляется от яда и получает жетон стойкости.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 106,
    title: "Зов предков",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Поменяйте эту карту на любую из сброса не глубже последних 10, но не ранее последних 3.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 107,
    title: "Швы",
    types: ["action", "effect"],
    qty: 4,
    group: "action",
    desc: "Любой выбранный активный игрок восстанавливает два жетона стойкости.",
    img: "cards/15_shvy.jpg"
  },
  {
    id: 108,
    title: "Сэппуку",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Вы умираете и отдаёте жетон чести другому игроку. Таким образом нельзя потерять последний жетон чести.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 109,
    title: "Саке",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Можете сбросить эту карту совместно с другими (максимум 3). За каждую сброшенную карту, включая эту, берёте новую карту из колоды.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 110,
    title: "Подсечка",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Другой выбранный игрок скидывает свою текущую стойку, за это вы берёте карту. Или можете сбросить эту карту, чтобы взять две новых из колоды.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 111,
    title: "Предательство",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Вы сбрасываете жетон чести в сброс, и за это получаете семь карт из колоды. Не считается смертью.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 112,
    title: "Сапёр",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Можете обезвредить любую ловушку на столе, за это вы берёте карту. Или можете сбросить эту карту, чтобы взять две новых из колоды.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 113,
    title: "Эквилибриум",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Количество жетонов жизни выбранного игрока становится равно вашему.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 114,
    title: "Передышка",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Восстановите все недостающие жетоны стойкости. Другой игрок на ваш выбор берёт одну карту из колоды.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 115,
    title: "Ясновидение",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Выбранный игрок показывает всем свои карты с руки до следующего действия.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 116,
    title: "Яд фугу",
    types: ["action", "effect"],
    qty: 1,
    group: "action",
    desc: "Отравляет выбранного активного игрока. Если игрок уже отравлен, он получает одну рану.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 117,
    title: "Обмен душ",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Вы меняетесь с выбранным игроком количеством жетонов стойкости.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 118,
    title: "Дайме",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Либо сыграйте эту карту, чтобы взять три новых из колоды, или оставьте, чтобы получить победное очко (кроме Ронина).",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 119,
    title: "Переливание крови",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Очищает любого игрока от отравления и передаёт его любому другому.",
    img: "cards/14_zov_predkov.jpg"
  },
  {
    id: 120,
    title: "Жертва крови",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Сыграв эту карту, берите за каждый сброшенный жетон стойкости (кроме последнего) новую карту из колоды.",
    img: "cards/14_zov_predkov.jpg"
  },

  // ── ВМЕШАТЕЛЬСТВА (стр. 17) ───────────────────────────────────────
  {
    id: 121,
    title: "Исцеление",
    types: ["intervention"],
    qty: 1,
    group: "intervention",
    desc: "ВМЕШАТЕЛЬСТВО. Восстановите все жетоны стойкости отравленному ядом игроку и снимите само отравление.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 122,
    title: "Смерть от фугу",
    types: ["intervention"],
    qty: 1,
    group: "intervention",
    desc: "ВМЕШАТЕЛЬСТВО. Сыграйте эту карту, чтобы нанести две раны отравленному ядом игроку.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 123,
    title: "Имбирь",
    types: ["intervention"],
    qty: 1,
    group: "intervention",
    desc: "ВМЕШАТЕЛЬСТВО. Сыграйте эту карту, чтобы восстановить любому игроку один жетон стойкости.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 124,
    title: "Удар дракона",
    types: ["intervention"],
    qty: 1,
    group: "intervention",
    desc: "ВМЕШАТЕЛЬСТВО. Сыграйте эту карту, чтобы нанести одну рану любому выбранному игроку.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 125,
    title: "Подвиг",
    types: ["intervention"],
    qty: 1,
    group: "intervention",
    desc: "ВМЕШАТЕЛЬСТВО. Сыграйте эту карту, чтобы перенаправить прямую атаку оружия на себя.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 126,
    title: "Рука помощи",
    types: ["intervention"],
    qty: 1,
    group: "intervention",
    desc: "ВМЕШАТЕЛЬСТВО. Сыграйте эту карту, чтобы обменяться в закрытую с любым игроком картами на ваше обоюдное усмотрение.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 127,
    title: "Весточка",
    types: ["intervention"],
    qty: 1,
    group: "intervention",
    desc: "ВМЕШАТЕЛЬСТВО. Сыграйте эту карту, чтобы передать любому игроку в закрытую любую другую карту из своей руки.",
    img: "cards/05_vmeshatelstvo.jpg"
  },
  {
    id: 128,
    title: "Симулянт",
    types: ["intervention", "effect"],
    qty: 1,
    group: "intervention",
    desc: "ВМЕШАТЕЛЬСТВО. ЭФФЕКТ. Выбранный игрок симулирует смерть, оставляя один жетон стойкости. Следующий раунд он обескровлен. В начале хода игрока эффект пропадает. Можно сыграть во время прямой атаки оружием по игроку.",
    img: "cards/05_vmeshatelstvo.jpg"
  },

  // ── ПРОЧИЕ ДЕЙСТВИЯ (стр. 18) ─────────────────────────────────────
  {
    id: 129,
    title: "Воровство",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Заберите одну случайную карту с руки любого активного игрока.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 130,
    title: "Кукла вуду",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Можете выбрать любой эффект на столе и переложить его на любого игрока.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 131,
    title: "Дурман",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Вы забираете выбранный эффект игрока на себя.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 132,
    title: "Сифон жизни",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Забираете у игрока жетон стойкости и добавляете его себе.",
    img: "cards/09_plagiat.jpg"
  },
  {
    id: 133,
    title: "Обман",
    types: ["action"],
    qty: 1,
    group: "action",
    desc: "Вы забираете ловушку другого игрока себе в руку.",
    img: "cards/09_plagiat.jpg"
  },

  // ── ПЕРСОНАЖИ (стр. 19) ───────────────────────────────────────────
  {
    id: 134,
    title: "Рюдзо Исикава — Мастер ближнего боя",
    types: ["character"],
    qty: 5,
    group: "character",
    desc: "Ваши атаки на расстоянии один наносят на одну рану больше. За каждую рану, полученную от оружия, вы берёте карту из колоды. Раз за ход можете обменять жетоны стойкости на новые карты из колоды.",
    img: "cards/01_geysha.jpg"
  },
  {
    id: 135,
    title: "Усивака — Безрассудный налётчик",
    types: ["character"],
    qty: 5,
    group: "character",
    desc: "Ваши атаки метательным оружием наносят на одну рану больше. Атаки по вам оружием с дальностью 1 наносят на одну рану меньше. Дайкю не имеет ограничений дальности.",
    img: "cards/06_yuna.jpg"
  },
  {
    id: 136,
    title: "Таранага Норио — Искусный стратег",
    types: ["character"],
    qty: 5,
    group: "character",
    desc: "В фазе набора вы берёте дополнительную карту и можете брать из сброса. В случае воровства или ошеломления и реакции на групповые действия, сами выбираете какую карту отдавать.",
    img: "cards/06_yuna.jpg"
  },
  {
    id: 137,
    title: "Кокоро — Непоколебимый великан",
    types: ["character"],
    qty: 5,
    group: "character",
    desc: "Вашу стойку не могут украсть или сбросить. Вы не теряете стойку при смерти. На вас не действуют карты, заставляющие сбросить случайную карту. Полностью деревянные оружия наносят дополнительную рану.",
    img: "cards/06_yuna.jpg"
  },
  {
    id: 138,
    title: "Хандзо — Неуловимый синоби",
    types: ["character"],
    qty: 4,
    group: "character",
    desc: "Ваши прямые атаки игнорируют ловушки. Вы можете сыграть карту оружия как карту защиты, при этом получая одну рану.",
    img: "cards/01_geysha.jpg"
  },
  {
    id: 139,
    title: "Иё — Знаток ловушек",
    types: ["character"],
    qty: 5,
    group: "character",
    desc: "Ваши ловушки не могут обезвредить, украсть или просветить. Вы можете воспользоваться активной ловушкой как защитой, потеряв бонусы от ловушки.",
    img: "cards/06_yuna.jpg"
  },
  {
    id: 140,
    title: "Така — Ловкая воровка",
    types: ["character"],
    qty: 5,
    group: "character",
    desc: "Вместо нанесения ран вы можете объявить, что будете воровать карты. Раз в ход вы можете сбросить три карты, чтобы взять две новых из колоды. У вас не могут воровать карты.",
    img: "cards/06_yuna.jpg"
  }
];

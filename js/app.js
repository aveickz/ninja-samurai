$(function () {

  // ── Мета типов ────────────────────────────────────────────────────
  var TYPE_META = {
    role:         { label: 'Роль',          color: '#9c6ec0' },
    action:       { label: 'Действие',      color: '#FFDDDD' },
    weapon:       { label: 'Оружие',        color: '#ED1C24' },
    trap:         { label: 'Ловушка',       color: '#5f8598' },
    character:    { label: 'Персонаж',      color: '#377cf4' },
    modifier:     { label: 'Модификатор',   color: '#ED1C24' },
    defense:      { label: 'Защита',        color: '#dca300' },
    stance:       { label: 'Стойка',        color: '#A78B6B' },
    effect:       { label: 'Эффект',        color: '#FFDDDD' },
    intervention: { label: 'Вмешательство', color: '#3B8476' },
    aoe:          { label: 'Групповая',     color: '#FFDDDD' }
  };

  var ALL_TYPES = Object.keys(TYPE_META);

  // ── Цвета верхней плашки по группе ───────────────────────────────
  var GROUP_TITLE_COLOR = {
    role:         '#5d3c75',
    defense:      '#dca300',
    trap:         '#43525A',
    weapon:       '#231F20',
    stance:       '#A78B6B',
    modifier:     '#ED1C24',
    aoe:          '#231F20',
    effect:       '#231F20',
    intervention: '#3B8476',
    character:    '#377cf4',
    action:       '#231F20',
    trash:        '#3a3a3a'
  };

  // ── Порядок и названия групп ──────────────────────────────────────
  // role идёт первой — это мета-карта (кто играет), не часть колоды.
  var GROUP_ORDER = [
    'role',
    'weapon', 'trap', 'defense', 'stance', 'modifier',
    'aoe', 'effect', 'action', 'intervention', 'character'
  ];

  var GROUP_LABELS = {
    role:         'Роли',
    weapon:       'Оружие',
    trap:         'Ловушки',
    defense:      'Защита',
    stance:       'Стойки',
    modifier:     'Модификаторы',
    aoe:          'Групповые',
    effect:       'Эффекты',
    action:       'Действия',
    intervention: 'Вмешательства',
    character:    'Персонажи',
    trash:        'Корзина'
  };

  // ── Игровые / неигровые карты ────────────────────────────────────
  // Карты групп role и character не разыгрываются — это мета-карты:
  // role обозначает сторону игрока, character — фон для персонажа.
  // В статистике процент рассчитывается только от игровых карт,
  // а сами неигровые группы выводятся отдельной секцией.
  var NON_PLAYABLE_GROUPS = ['role', 'character'];

  /**
   * Является ли карта игровой (учитывается в основном пуле колоды).
   * Вычисляемое на лету свойство — не храним в данных карточки.
   */
  function isPlayable(card) {
    return NON_PLAYABLE_GROUPS.indexOf(card.group) === -1;
  }

  // ── Состояние фильтра ─────────────────────────────────────────────
  // activeMode: null = все, '__poison__' = яд, '__print__' = на печать,
  //             или строка типа ('weapon', 'trap', …)
  var activeMode = null;

  // ── Типографика: неразрывный пробел после коротких слов ──────────
  // Возвращает HTML-строку — вставлять через .html(), не .text()
  function typograph(text) {
    if (!text) return '';
    // Экранируем HTML-спецсимволы (desc не содержит разметки)
    var escaped = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
    // После слова из 1–2 букв (кириллица или латиница) + пробел → &nbsp;
    return escaped.replace(/(\s|^)([А-ЯЁа-яёA-Za-z]{1,2}) /g, '$1$2&nbsp;');
  }

  // ── Построение блока описания карточки ───────────────────────────
  // Если в desc встречается конструкция "-ИЛИ-" (с любыми пробелами
  // вокруг), описание разбивается на части, между которыми рисуется
  // компактный аналог .group-divider — горизонтальные линии и слово
  // «ИЛИ» по центру. CSS — в card.css.
  function buildDescContent(desc) {
    var parts = String(desc).split(/\s*-ИЛИ-\s*/)
      .map(function (p) { return p.replace(/^\s+|\s+$/g, ''); })
      .filter(function (p) { return p.length > 0; });

    if (parts.length <= 1) {
      return $('<div>', { class: 'card-desc' }).html(typograph(desc));
    }

    var $wrap = $('<div>', { class: 'card-desc card-desc--split' });
    parts.forEach(function (part, i) {
      if (i > 0) {
        $wrap.append(
          $('<div>', { class: 'card-desc-or' }).append(
            $('<span>', { class: 'card-desc-or-line' }),
            $('<span>', { class: 'card-desc-or-label', text: 'ИЛИ' }),
            $('<span>', { class: 'card-desc-or-line' })
          )
        );
      }
      $wrap.append(
        $('<div>', { class: 'card-desc-part' }).html(typograph(part))
      );
    });
    return $wrap;
  }

  // ── Построение тегов типов на карточке ───────────────────────────
  function buildTypeTags(types, tags) {
    var $wrap = $('<div>', { class: 'card-types' });
    $.each(types, function (_, t) {
      var meta = TYPE_META[t] || { label: t, color: '#555' };
      $('<span>', {
        class: 'type-tag',
        text: meta.label,
        css: { '--tag-color': meta.color }
      }).appendTo($wrap);
    });
    if (tags.indexOf('poison') !== -1) {
      $('<span>', { class: 'type-tag type-tag--poison', text: 'Яд' }).appendTo($wrap);
    }
    if (tags.indexOf('toPrint') !== -1) {
      $('<span>', { class: 'type-tag type-tag--print', text: 'На печать' }).appendTo($wrap);
    }
    if (tags.indexOf('draft') !== -1) {
      $('<span>', { class: 'type-tag type-tag--draft', text: 'Черновик' }).appendTo($wrap);
    }
    if (tags.indexOf('trash') !== -1) {
      $('<span>', { class: 'type-tag type-tag--trash', text: 'Корзина' }).appendTo($wrap);
    }
    return $wrap;
  }

  // ── Построение карточки ───────────────────────────────────────────
  function buildCard(card) {
    var typeClasses = $.map(card.types, function (t) { return 'type-' + t; }).join(' ');

    // Внутренний блок арта — маска + заголовок + описание
    var $card = $('<div>', { class: 'card' }).append(

      // Слой 0: фон группы (только для weapon)
      card.group === 'weapon'
        ? $('<img>', { class: 'card-bg', src: card.tags.indexOf('poison') !== -1 ? 'media/weapon_bg_poisoned.png' : 'media/weapon_bg.png', alt: '', draggable: false })
        : null,

      // Слой 1: арт (самый нижний)
      $('<img>', { class: 'card-art', src: card.img, alt: card.title, loading: 'lazy' })
        .on('load', function () {
          // После загрузки арта выставляем top у card-desc-wrap = нижнему краю арта,
          // но не выше минимума, нужного для вмещения текста описания.
          var $img = $(this);
          var $card = $img.closest('.card');
          var $wrap = $card.find('.card-desc-wrap');
          if (!$wrap.length) return;

          var cardH    = $card[0].offsetHeight;
          var artBottom = $img[0].offsetTop + $img[0].offsetHeight;

          // Измеряем минимальную высоту: убираем top-ограничение, даём блоку
          // сжаться до содержимого, читаем scrollHeight, потом восстанавливаем.
          $wrap.css('top', '');
          var minH = $wrap[0].scrollHeight;

          // top не должен быть ниже (cardH - minH), иначе текст не влезет
          var topPx = Math.min(artBottom, cardH - minH);
          $wrap.css('top', ( (topPx / cardH * 100) - 2.5).toFixed(3) + '%');
        }),

      // Слой 2: иконки из icons[] — вертикальный стек в левом верхнем углу арта
      card.icons && card.icons.length
        ? $('<div>', { class: 'card-icons' }).append(
            $.map(card.icons, function (icon) {
              return $('<img>', {
                class: 'card-icon',
                src: 'media/' + icon + '.png',
                alt: icon,
                draggable: false
              });
            })
          )
        : null,

      // Слой 3: маска/рамка поверх арта
      $('<img>', { class: 'card-mask', src: 'media/mask.png', alt: '', draggable: false }),

      // Слой 3: заголовок в верхней полосе маски
      $('<div>', {
        class: 'card-title-wrap',
        // Приоритет: card.titleBgColor (per-card override) → GROUP_TITLE_COLOR
        // по группе → дефолтный почти-чёрный.
        css: { background: card.titleBgColor || GROUP_TITLE_COLOR[card.group] || '#231F20' }
      }).append(
        $('<span>', { class: 'card-title', text: card.title }),
        card.subtitle
          ? $('<span>', { class: 'card-subtitle', text: card.subtitle })
          : null
      ),

      // Слой HP: иконка сердца с числом — только для персонажей
      card.hp != null
        ? $('<div>', { class: 'card-hp' }).append(
            $('<img>', { class: 'card-hp-img', src: 'media/hp.png', alt: '', draggable: false }),
            $('<span>', { class: 'card-hp-value', text: card.hp })
          )
        : null,

      // Слой 5: иконка группы — поверх маски, по центру низа плашки заголовка
      // Если для группы нет media/<group>.png (например, новая группа без
      // иконки), .on('error') скрывает <img> вместо показа ломаной картинки.
      $('<img>', {
        class: 'card-group-icon',
        src: 'media/' + (card.group === 'effect' ? 'effect8' : card.group) + '.png',
        alt: '',
        draggable: false
      }).on('error', function () { $(this).hide(); }),

      // Слой 4: жёлтая плашка с описанием внизу (только если есть текст)
      card.desc ? $('<div>', { class: 'card-desc-wrap' }).append(
        $('<img>', { class: 'card-delimiter', src: 'media/delimiter.png', alt: '', draggable: false }),
        buildDescContent(card.desc)
      ) : null
    );

    // Внешний контейнер: card + footer (типы слева, qty справа)
    var $footer = $('<div>', { class: 'card-footer' }).append(
      buildTypeTags(card.types, card.tags || []),
      $('<div>', { class: 'card-qty', text: '×' + (card.qty || 1) })
    );

    var $item = $('<div>', {
      // card-character — отдельный модификатор для карт-персонажей,
      // позволяет CSS-правилам подменять стили внутри (например, цвет
      // заголовка). Добавляется только когда group === 'character'.
      class: 'card-item ' + typeClasses +
             (card.group === 'character' ? ' card-character' : ''),
      'data-card-id': card.id,
      'data-types': card.types.join(' '),
      'data-group': card.group || 'action',
      'data-qty': card.qty || 1,
      'data-tags': (card.tags || []).join(' ')
    }).append(
      $card,
      $footer
    );

    $item.on('click', function (e) {
      var $this = $(this);
      var isOpen = $this.hasClass('is-zoomed');

      // Закрыть все остальные
      $('.card-item.is-zoomed').not($this).removeClass('is-zoomed');

      // Переключить текущую
      $this.toggleClass('is-zoomed', !isOpen);

      // Клик вне карточки — закрыть
      if (!isOpen) {
        e.stopPropagation();
      }
    });

    return $item;
  }

  // ── Разделитель группы ────────────────────────────────────────────
  function buildGroupDivider(groupKey) {
    var label = GROUP_LABELS[groupKey] || groupKey;
    var color = (TYPE_META[groupKey] || {}).color || '#7a5a2a';
    return $('<div>', {
      class: 'group-divider',
      'data-group-divider': groupKey,
      css: { '--group-color': color }
    }).append(
      $('<div>', { class: 'group-divider-line' }),
      $('<span>', { class: 'group-divider-label', text: label }),
      $('<div>', { class: 'group-divider-line' })
    );
  }

  // ── Рендер: всё в $grid с разделителями ──────────────────────────
  var $grid = $('#grid');

  // Группируем все карты по group (включая trash — они нужны в обоих местах)
  var grouped = {};
  $.each(CARDS, function (_, card) {
    var g = card.group || 'action';
    if (!grouped[g]) grouped[g] = [];
    grouped[g].push(card);
  });

  // Рендерим группу за группой.
  // Trash-карты попадают сюда тоже, но помечаются data-trash-real="1"
  // и по умолчанию скрыты — показываются только при активном __trash__ фильтре.
  $.each(GROUP_ORDER, function (_, groupKey) {
    var cards = grouped[groupKey];
    if (!cards || cards.length === 0) return;

    $grid.append(buildGroupDivider(groupKey));

    $.each(cards, function (_, card) {
      var $item = buildCard(card);
      if ((card.tags || []).indexOf('trash') !== -1) {
        $item.attr('data-trash-real', '1').addClass('card--hidden');
      }
      $grid.append($item);
    });
  });

  // Псевдо-группа «Корзина» — те же trash-карты, помечены data-trash-pseudo="1"
  // По умолчанию видимы; скрываются при активном __trash__ фильтре.
  var trashCards = CARDS.filter(function (card) {
    return (card.tags || []).indexOf('trash') !== -1;
  });
  if (trashCards.length > 0) {
    $grid.append(buildGroupDivider('trash'));
    $.each(trashCards, function (_, card) {
      $grid.append(buildCard(card).attr('data-trash-pseudo', '1'));
    });
  }

  // ── Фильтрация ────────────────────────────────────────────────────
  function applyFilter() {
    var totalTypes = 0;
    var totalQty = 0;
    var visibleByGroup = {};
    var isTrashMode = activeMode === '__trash__';

    $('#grid .card-item').each(function () {
      var $el       = $(this);
      var isReal    = !!$el.attr('data-trash-real');
      var isPseudo  = !!$el.attr('data-trash-pseudo');
      var cardTypes = $el.data('types').split(' ');
      var cardTags  = ($el.data('tags') || '').toString().split(' ');

      var visible;

      if (isPseudo) {
        // Pseudo-копии в Корзине: скрыты в __trash__ режиме,
        // иначе фильтруются так же как обычные карты
        if (isTrashMode) {
          visible = false;
        } else if (activeMode === '__poison__') {
          visible = cardTags.indexOf('poison') !== -1;
        } else if (activeMode === '__print__') {
          visible = cardTags.indexOf('toPrint') !== -1;
        } else if (activeMode === '__draft__') {
          visible = cardTags.indexOf('draft') !== -1;
        } else if (activeMode === '__comments__') {
          visible = $el.attr('data-has-comments') === '1';
        } else if (activeMode) {
          visible = cardTypes.indexOf(activeMode) !== -1;
        } else {
          visible = true;
        }

      } else if (isReal) {
        // Real-копии в родных группах: видны только когда активен __trash__ фильтр
        visible = isTrashMode;

      } else {
        // Обычные карты (не trash): стандартная логика фильтрации
        if (isTrashMode) {
          visible = false;
        } else if (activeMode === '__poison__') {
          visible = cardTags.indexOf('poison') !== -1;
        } else if (activeMode === '__print__') {
          visible = cardTags.indexOf('toPrint') !== -1;
        } else if (activeMode === '__draft__') {
          visible = cardTags.indexOf('draft') !== -1;
        } else if (activeMode === '__comments__') {
          // data-has-comments проставляется в comments.js после
          // bucket.list: '1' если у карточки есть комментарии, иначе атрибут
          // отсутствует. Если comments-модуль не загружен, фильтр пуст.
          visible = $el.attr('data-has-comments') === '1';
        } else if (activeMode) {
          visible = cardTypes.indexOf(activeMode) !== -1;
        } else {
          visible = true;
        }
      }

      $el.toggleClass('card--hidden', !visible);
      if (visible) {
        totalTypes++;
        totalQty += parseInt($el.data('qty'), 10) || 1;
        var g = isPseudo ? 'trash' : $el.data('group');
        visibleByGroup[g] = (visibleByGroup[g] || 0) + 1;
      }
    });

    // Показываем разделитель только если в группе есть видимые карточки
    $('[data-group-divider]').each(function () {
      var g = $(this).data('group-divider');
      $(this).toggleClass('group-divider--hidden', !visibleByGroup[g]);
    });

    // Переупорядочиваем группы: при активном type-фильтре группа,
    // соответствующая фильтру, идёт первой
    var isTypeFilter = activeMode && activeMode.indexOf('__') !== 0;
    $('[data-group-divider]').each(function () {
      $(this).css('order', '');
    });
    $('#grid .card-item').each(function () {
      $(this).css('order', '');
    });
    if (isTypeFilter) {
      $('[data-group-divider]').each(function () {
        var g = $(this).data('group-divider');
        $(this).css('order', g === activeMode ? -2 : '');
      });
      $('#grid .card-item').each(function () {
        var $el = $(this);
        var g = $el.attr('data-trash-pseudo') ? 'trash' : $el.data('group');
        $el.css('order', g === activeMode ? -1 : '');
      });
    }

    $('.count').text(totalTypes + ' видов · ' + totalQty + ' карт');

    // Подсветка активных кнопок
    $('.filter-btn').each(function () {
      var t = $(this).data('type');
      if (t === '__all__') {
        $(this).toggleClass('active', activeMode === null);
      } else {
        $(this).toggleClass('active', activeMode === t);
      }
    });
  }

  // ── Вспомогательная: установить фильтр и записать в hash ─────────
  var VALID_MODES = ALL_TYPES.concat(['__poison__', '__print__', '__draft__', '__trash__', '__comments__']);

  function setFilter(mode) {
    activeMode = mode;
    location.hash = mode ? mode : '';
    applyFilter();
  }

  // ── Публичный API фильтра — для comments.js и прочих расширений ───
  window.CardFilter = {
    setMode:    function (mode) { setFilter(mode || null); },
    toggleMode: function (mode) { setFilter(activeMode === mode ? null : mode); },
    getMode:    function () { return activeMode; },
    apply:      function () { applyFilter(); }
  };

  // ── Строим панель фильтров ────────────────────────────────────────
  function buildFilters() {
    var $bar = $('#filter-bar');

    // ── Ряд 1: «Все» ─────────────────────────────────────────────────
    var $row1 = $('<div>', { class: 'filter-row' }).appendTo($bar);
    $('<button>', { class: 'filter-btn active', text: 'Все', 'data-type': '__all__' })
      .on('click', function () { setFilter(null); })
      .appendTo($row1);

    // ── Ряд 2: фильтры по группам ────────────────────────────────────
    // Кнопки идут в порядке убывания количества карт с этим типом
    // (по уникальным id — qty не учитывается). Так у пользователя
    // под рукой самые «толстые» категории, а редкие (Роли, и т.п.)
    // отъезжают вправо.
    var typeCounts = {};
    $.each(ALL_TYPES, function (_, t) { typeCounts[t] = 0; });
    $.each(CARDS, function (_, card) {
      $.each(card.types || [], function (_, t) {
        if (typeCounts[t] != null) typeCounts[t] += 1;
      });
    });
    var sortedTypes = ALL_TYPES.slice().sort(function (a, b) {
      // Сначала count убывая; при равенстве — стабильно по исходному порядку
      // в TYPE_META (через индекс).
      var diff = typeCounts[b] - typeCounts[a];
      if (diff !== 0) return diff;
      return ALL_TYPES.indexOf(a) - ALL_TYPES.indexOf(b);
    });

    var $row2 = $('<div>', { class: 'filter-row' }).appendTo($bar);
    $.each(sortedTypes, function (_, t) {
      var meta = TYPE_META[t];
      $('<button>', {
        class: 'filter-btn',
        text: meta.label,
        'data-type': t,
        css: { '--tag-color': meta.color }
      })
        .on('click', function () {
          setFilter(activeMode === t ? null : t);
        })
        .appendTo($row2);
    });

    // ── Ряд 3: фильтры по тегам ──────────────────────────────────────
    var $row3 = $('<div>', { class: 'filter-row' }).appendTo($bar);

    $('<button>', { class: 'filter-btn filter-btn--poison', text: '☠ Яд', 'data-type': '__poison__' })
      .on('click', function () {
        setFilter(activeMode === '__poison__' ? null : '__poison__');
      })
      .appendTo($row3);

    $('<button>', { class: 'filter-btn filter-btn--print', text: '🖨 На печать', 'data-type': '__print__' })
      .on('click', function () {
        setFilter(activeMode === '__print__' ? null : '__print__');
      })
      .appendTo($row3);

    $('<button>', { class: 'filter-btn filter-btn--draft', text: '✏ Черновик', 'data-type': '__draft__' })
      .on('click', function () {
        setFilter(activeMode === '__draft__' ? null : '__draft__');
      })
      .appendTo($row3);

    $('<button>', { class: 'filter-btn filter-btn--trash', text: '🗑 Корзина', 'data-type': '__trash__' })
      .on('click', function () {
        setFilter(activeMode === '__trash__' ? null : '__trash__');
      })
      .appendTo($row3);
  }

  // ── Закрытие зума кликом вне карточки или Escape ──────────────────
  $(document).on('click', function () {
    $('.card-item.is-zoomed').removeClass('is-zoomed');
  });
  $(document).on('keydown', function (e) {
    if (e.key === 'Escape') $('.card-item.is-zoomed').removeClass('is-zoomed');
  });

  // ── Статистика в шапке (общая, не зависит от фильтра) ───────────
  // Считаем только активные карты (без trash и draft)
  var activeCards = CARDS.filter(function (c) {
    var tags = c.tags || [];
    return tags.indexOf('trash') === -1 && tags.indexOf('draft') === -1;
  });
  $('#stat-types').text(activeCards.length);
  $('#stat-total').text(activeCards.reduce(function (sum, c) { return sum + (c.qty || 1); }, 0));

  // ── Статическая статистика по CARDS ──────────────────────────────
  function buildStats() {
    // Активные карты (без trash и draft) — для основной статистики
    var totalQty   = activeCards.reduce(function (sum, c) { return sum + (c.qty || 1); }, 0);
    var totalTypes = activeCards.length;

    // Делим активные карты на игровые и неигровые
    var playableCards = activeCards.filter(isPlayable);
    var otherCards    = activeCards.filter(function (c) { return !isPlayable(c); });

    var playableTypes = playableCards.length;
    var playableQty   = playableCards.reduce(function (s, c) { return s + (c.qty || 1); }, 0);
    var otherTypes    = otherCards.length;
    var otherQty      = otherCards.reduce(function (s, c) { return s + (c.qty || 1); }, 0);

    $('#stat-playable-types').text(playableTypes);
    $('#stat-playable-qty').text(playableQty);
    $('#stat-other-types').text(otherTypes);
    $('#stat-other-qty').text(otherQty);

    // Считаем по группам — только активные карты
    var groupStats = {};
    $.each(activeCards, function (_, card) {
      var g = card.group || 'action';
      if (!groupStats[g]) groupStats[g] = { types: 0, qty: 0 };
      groupStats[g].types++;
      groupStats[g].qty += card.qty || 1;
    });

    var $tbody = $('#stats-table-body');
    // Сортируем группы по убыванию qty (колонка «Карт»). Тай-брейк —
    // индекс в GROUP_ORDER, чтобы порядок при равенстве оставался
    // стабильным и предсказуемым.
    var sortedGroups = GROUP_ORDER.slice()
      .filter(function (g) { return !!groupStats[g]; })
      .sort(function (a, b) {
        var diff = groupStats[b].qty - groupStats[a].qty;
        if (diff !== 0) return diff;
        return GROUP_ORDER.indexOf(a) - GROUP_ORDER.indexOf(b);
      });
    $.each(sortedGroups, function (_, g) {
      var s = groupStats[g];
      var groupIsPlayable = NON_PLAYABLE_GROUPS.indexOf(g) === -1;
      // Процент считаем только от игровых карт; неигровые группы
      // (Роли, Персонажи) показывают «—» — они в общий пул не входят.
      var pct = groupIsPlayable
        ? (playableQty > 0 ? (s.qty / playableQty * 100).toFixed(1) + '%' : '—')
        : '—';
      $('<tr>', {
        class: groupIsPlayable ? '' : 'stats-row--non-playable'
      }).append(
        $('<td>', { text: GROUP_LABELS[g] || g }),
        $('<td>', { text: s.types }),
        $('<td>', { text: s.qty }),
        $('<td>', { text: pct })
      ).appendTo($tbody);
    });

    // Псевдо-группы Draft и Trash — считаем отдельно, без % от общего
    var pseudoGroups = [
      { key: 'draft', label: GROUP_LABELS['draft'] || 'Черновик' },
      { key: 'trash', label: GROUP_LABELS['trash'] || 'Корзина' }
    ];
    $.each(pseudoGroups, function (_, pg) {
      var cards = CARDS.filter(function (c) { return (c.tags || []).indexOf(pg.key) !== -1; });
      if (!cards.length) return;
      var qty = cards.reduce(function (sum, c) { return sum + (c.qty || 1); }, 0);
      $('<tr>', { class: 'stats-row--pseudo' }).append(
        $('<td>', { text: pg.label }),
        $('<td>', { text: cards.length }),
        $('<td>', { text: qty }),
        $('<td>', { text: '—' })
      ).appendTo($tbody);
    });

    // ── Соотношение оружия к защите (только активные карты) ─────────
    var weaponQty = 0, defenseQty = 0;
    $.each(activeCards, function (_, card) {
      var qty = card.qty || 1;
      if (card.types.indexOf('weapon') !== -1)  weaponQty  += qty;
      if (card.types.indexOf('defense') !== -1) defenseQty += qty;
    });
    var ratio = defenseQty > 0 ? (weaponQty / defenseQty).toFixed(2) : '—';

    var ratioText = 'Оружие (' + weaponQty + ') / Защита (' + defenseQty + ') = ' + ratio + ' : 1';
    $('#stats-ratio').remove();
    $('<div>', { id: 'stats-ratio', class: 'stats-ratio' }).append(
      $('<p>', { class: 'stats-ratio-title', text: 'Оружие vs Защита' }),
      $('<p>', { class: 'stats-ratio-value', text: ratioText })
    ).appendTo('.sidebar-stats');
  }

  // ── Печать: группируем карточки по 9 на страницу ─────────────────
  function wrapForPrint() {
    var $cards = $('#grid .card-item:not(.card--hidden)');
    var pages = [];
    for (var i = 0; i < $cards.length; i += 9) {
      pages.push($cards.slice(i, i + 9));
    }
    // Оборачиваем каждую группу в .print-page
    $.each(pages, function (_, $group) {
      $group.wrapAll('<div class="print-page"></div>');
    });
  }

  function unwrapAfterPrint() {
    $('.print-page').each(function () {
      $(this).replaceWith($(this).children());
    });
  }

  window.addEventListener('beforeprint', wrapForPrint);
  window.addEventListener('afterprint', unwrapAfterPrint);

  // ── Инициализация ─────────────────────────────────────────────────
  buildFilters();
  buildStats();

  // Восстанавливаем фильтр из hash (если он валидный)
  var hashMode = location.hash.replace(/^#/, '');
  if (hashMode && VALID_MODES.indexOf(hashMode) !== -1) {
    activeMode = hashMode;
  }
  applyFilter();

});

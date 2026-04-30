$(function () {

  // ── Мета типов ────────────────────────────────────────────────────
  var TYPE_META = {
    action:       { label: 'Действие',      color: '#FFDDDD' },
    weapon:       { label: 'Оружие',        color: '#ED1C24' },
    trap:         { label: 'Ловушка',       color: '#5f8598' },
    character:    { label: 'Персонаж',      color: '#6C8CC7' },
    modifier:     { label: 'Модификатор',   color: '#ED1C24' },
    defense:      { label: 'Защита',        color: '#dca300' },
    stance:       { label: 'Стойка',        color: '#A78B6B' },
    effect:       { label: 'Эффект',        color: '#FFDDDD' },
    intervention: { label: 'Вмешательство', color: '#3B8476' },
    group:        { label: 'Групповая',     color: '#FFDDDD' }
  };

  var ALL_TYPES = Object.keys(TYPE_META);

  // ── Цвета верхней плашки по группе ───────────────────────────────
  var GROUP_TITLE_COLOR = {
    defense:      '#dca300',
    trap:         '#43525A',
    weapon:       '#231F20',
    stance:       '#A78B6B',
    modifier:     '#ED1C24',
    group:        '#231F20',
    effect:       '#231F20',
    intervention: '#3B8476',
    character:    '#6C8CC7',
    action:       '#231F20'
  };

  // ── Порядок и названия групп ──────────────────────────────────────
  var GROUP_ORDER = [
    'weapon', 'trap', 'defense', 'stance', 'modifier',
    'group', 'effect', 'action', 'intervention', 'character'
  ];

  var GROUP_LABELS = {
    weapon:       'Оружие',
    trap:         'Ловушки',
    defense:      'Защита',
    stance:       'Стойки',
    modifier:     'Модификаторы',
    group:        'Групповые',
    effect:       'Эффекты',
    action:       'Действия',
    intervention: 'Вмешательства',
    character:    'Персонажи'
  };

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
        css: { background: GROUP_TITLE_COLOR[card.group] || '#231F20' }
      }).append(
        $('<span>', { class: 'card-title', text: card.title })
      ),

      // Слой 4: жёлтая плашка с описанием внизу (только если есть текст)
      card.desc ? $('<div>', { class: 'card-desc-wrap' }).append(
        $('<img>', { class: 'card-delimiter', src: 'media/delimiter.png', alt: '', draggable: false }),
        $('<div>', { class: 'card-desc' }).html(typograph(card.desc))
      ) : null
    );

    // Внешний контейнер: card + footer (типы слева, qty справа)
    var $footer = $('<div>', { class: 'card-footer' }).append(
      buildTypeTags(card.types, card.tags || []),
      $('<div>', { class: 'card-qty', text: '×' + (card.qty || 1) })
    );

    var $item = $('<div>', {
      class: 'card-item ' + typeClasses,
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

  // Группируем карты по group в правильном порядке
  var grouped = {};
  $.each(CARDS, function (_, card) {
    var g = card.group || 'action';
    if (!grouped[g]) grouped[g] = [];
    grouped[g].push(card);
  });

  // Рендерим группу за группой
  $.each(GROUP_ORDER, function (_, groupKey) {
    var cards = grouped[groupKey];
    if (!cards || cards.length === 0) return;

    $grid.append(buildGroupDivider(groupKey));

    $.each(cards, function (_, card) {
      $grid.append(buildCard(card));
    });
  });

  // ── Фильтрация ────────────────────────────────────────────────────
  function applyFilter() {
    var totalTypes = 0;
    var totalQty = 0;
    var visibleByGroup = {};

    $('#grid .card-item').each(function () {
      var cardTypes = $(this).data('types').split(' ');
      var cardTags  = ($(this).data('tags') || '').toString().split(' ');

      var visible;
      if (activeMode === '__poison__') {
        visible = cardTags.indexOf('poison') !== -1;
      } else if (activeMode === '__print__') {
        visible = cardTags.indexOf('toPrint') !== -1;
      } else if (activeMode === '__draft__') {
        visible = cardTags.indexOf('draft') !== -1;
      } else if (activeMode === '__trash__') {
        visible = cardTags.indexOf('trash') !== -1;
      } else if (activeMode) {
        visible = cardTypes.indexOf(activeMode) !== -1;
      } else {
        visible = true;
      }

      $(this).toggleClass('card--hidden', !visible);
      if (visible) {
        totalTypes++;
        totalQty += parseInt($(this).data('qty'), 10) || 1;
        var g = $(this).data('group');
        visibleByGroup[g] = (visibleByGroup[g] || 0) + 1;
      }
    });

    // Показываем разделитель только если в группе есть видимые карточки
    $('[data-group-divider]').each(function () {
      var g = $(this).data('group-divider');
      $(this).toggleClass('group-divider--hidden', !visibleByGroup[g]);
    });

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

  // ── Строим панель фильтров ────────────────────────────────────────
  function buildFilters() {
    var $bar = $('#filter-bar');

    // Кнопка «Все»
    $('<button>', { class: 'filter-btn active', text: 'Все', 'data-type': '__all__' })
      .on('click', function () {
        activeMode = null;
        applyFilter();
      })
      .appendTo($bar);

    // Кнопка «Яд» (эксклюзивный режим)
    $('<button>', {
      class: 'filter-btn filter-btn--poison',
      text: '☠ Яд',
      'data-type': '__poison__'
    })
      .on('click', function () {
        activeMode = activeMode === '__poison__' ? null : '__poison__';
        applyFilter();
      })
      .appendTo($bar);

    // Кнопка «На печать» (эксклюзивный режим)
    $('<button>', {
      class: 'filter-btn filter-btn--print',
      text: '🖨 На печать',
      'data-type': '__print__'
    })
      .on('click', function () {
        activeMode = activeMode === '__print__' ? null : '__print__';
        applyFilter();
      })
      .appendTo($bar);

    // Кнопка «Черновик» (эксклюзивный режим)
    $('<button>', {
      class: 'filter-btn filter-btn--draft',
      text: '✏ Черновик',
      'data-type': '__draft__'
    })
      .on('click', function () {
        activeMode = activeMode === '__draft__' ? null : '__draft__';
        applyFilter();
      })
      .appendTo($bar);

    // Кнопка «Корзина» (эксклюзивный режим)
    $('<button>', {
      class: 'filter-btn filter-btn--trash',
      text: '🗑 Корзина',
      'data-type': '__trash__'
    })
      .on('click', function () {
        activeMode = activeMode === '__trash__' ? null : '__trash__';
        applyFilter();
      })
      .appendTo($bar);

    // Кнопка на каждый тип (эксклюзивный режим)
    $.each(ALL_TYPES, function (_, t) {
      var meta = TYPE_META[t];
      $('<button>', {
        class: 'filter-btn',
        text: meta.label,
        'data-type': t,
        css: { '--tag-color': meta.color }
      })
        .on('click', function () {
          activeMode = activeMode === t ? null : t;
          applyFilter();
        })
        .appendTo($bar);
    });
  }

  // ── Закрытие зума кликом вне карточки или Escape ──────────────────
  $(document).on('click', function () {
    $('.card-item.is-zoomed').removeClass('is-zoomed');
  });
  $(document).on('keydown', function (e) {
    if (e.key === 'Escape') $('.card-item.is-zoomed').removeClass('is-zoomed');
  });

  // ── Статистика в шапке (общая, не зависит от фильтра) ───────────
  $('#stat-types').text(CARDS.length);
  $('#stat-total').text(CARDS.reduce(function (sum, c) { return sum + (c.qty || 1); }, 0));

  // ── Статическая статистика по CARDS ──────────────────────────────
  function buildStats() {
    var totalQty = CARDS.reduce(function (sum, c) { return sum + (c.qty || 1); }, 0);
    var totalTypes = CARDS.length;

    $('#stat-types-live').text(totalTypes);
    $('#stat-qty-live').text(totalQty);

    // Считаем по группам из массива CARDS (не из DOM)
    var groupStats = {};
    $.each(CARDS, function (_, card) {
      var g = card.group || 'action';
      if (!groupStats[g]) groupStats[g] = { types: 0, qty: 0 };
      groupStats[g].types++;
      groupStats[g].qty += card.qty || 1;
    });

    var $tbody = $('#stats-table-body');
    $.each(GROUP_ORDER, function (_, g) {
      if (!groupStats[g]) return;
      var s = groupStats[g];
      var pct = (s.qty / totalQty * 100).toFixed(1) + '%';
      var color = GROUP_TITLE_COLOR[g] || '#7a5a2a';
      $('<tr>').append(
        $('<td>', { text: GROUP_LABELS[g] || g }),
        $('<td>', { text: s.types }),
        $('<td>', { text: s.qty }),
        $('<td>', { text: pct })
      ).appendTo($tbody);
    });

    // ── Соотношение оружия к защите ──────────────────────────────────
    var weaponQty = 0, defenseQty = 0;
    $.each(CARDS, function (_, card) {
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

  // ── Инициализация ─────────────────────────────────────────────────
  buildFilters();
  buildStats();
  applyFilter();

});

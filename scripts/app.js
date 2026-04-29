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
    group:        'Групповые действия',
    effect:       'Эффекты',
    action:       'Действия',
    intervention: 'Вмешательства',
    character:    'Персонажи'
  };

  // ── Состояние фильтра ─────────────────────────────────────────────
  // activeFilters — Set активных типов; пусто = показывать все
  var activeFilters = new Set();

  // ── Построение тегов типов на карточке ───────────────────────────
  function buildTypeTags(types) {
    var $wrap = $('<div>', { class: 'card-types' });
    $.each(types, function (_, t) {
      var meta = TYPE_META[t] || { label: t, color: '#555' };
      $('<span>', {
        class: 'type-tag',
        text: meta.label,
        css: { '--tag-color': meta.color }
      }).appendTo($wrap);
    });
    return $wrap;
  }

  // ── Построение карточки ───────────────────────────────────────────
  function buildCard(card) {
    var typeClasses = $.map(card.types, function (t) { return 'type-' + t; }).join(' ');

    // Внутренний блок арта — маска + заголовок + описание
    var $card = $('<div>', { class: 'card' }).append(

      // Слой 1: арт (самый нижний)
      $('<img>', { class: 'card-art', src: card.img, alt: card.title, loading: 'lazy' }),

      // Слой 2: маска/рамка поверх арта
      $('<img>', { class: 'card-mask', src: 'mask.png', alt: '', draggable: false }),

      // Слой 3: заголовок в верхней полосе маски
      $('<div>', {
        class: 'card-title-wrap',
        css: { background: GROUP_TITLE_COLOR[card.group] || '#231F20' }
      }).append(
        $('<span>', { class: 'card-title', text: card.title })
      ),

      // Слой 4: жёлтая плашка с описанием внизу
      $('<div>', { class: 'card-desc-wrap' }).append(
        $('<img>', { class: 'card-delimiter', src: 'delimiter.png', alt: '', draggable: false }),
        $('<div>', { class: 'card-desc', text: card.desc })
      )
    );

    // Внешний контейнер: card + footer (типы слева, qty справа)
    var $footer = $('<div>', { class: 'card-footer' }).append(
      buildTypeTags(card.types),
      $('<div>', { class: 'card-qty', text: '×' + (card.qty || 1) })
    );

    var $item = $('<div>', {
      class: 'card-item ' + typeClasses,
      'data-types': card.types.join(' '),
      'data-group': card.group || 'action',
      'data-qty': card.qty || 1
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
    var isAll = activeFilters.size === 0;

    // Показываем/скрываем разделители
    $('[data-group-divider]').each(function () {
      $(this).toggleClass('group-divider--hidden', !isAll);
    });

    $('#grid .card-item').each(function () {
      var cardTypes = $(this).data('types').split(' ');
      var visible = isAll ||
        cardTypes.some(function (t) { return activeFilters.has(t); });
      $(this).toggleClass('card--hidden', !visible);
      if (visible) {
        totalTypes++;
        totalQty += parseInt($(this).data('qty'), 10) || 1;
      }
    });
    $('.count').text(totalTypes + ' видов · ' + totalQty + ' карт в колоде');

    // Подсветка активных кнопок
    $('.filter-btn').each(function () {
      var t = $(this).data('type');
      if (t === '__all__') {
        $(this).toggleClass('active', activeFilters.size === 0);
      } else {
        $(this).toggleClass('active', activeFilters.has(t));
      }
    });
  }

  // ── Строим панель фильтров ────────────────────────────────────────
  function buildFilters() {
    var $bar = $('#filter-bar');

    // Кнопка «Все»
    $('<button>', { class: 'filter-btn active', text: 'Все', 'data-type': '__all__' })
      .on('click', function () {
        activeFilters.clear();
        applyFilter();
      })
      .appendTo($bar);

    // Кнопка на каждый тип
    $.each(ALL_TYPES, function (_, t) {
      var meta = TYPE_META[t];
      $('<button>', {
        class: 'filter-btn',
        text: meta.label,
        'data-type': t,
        css: { '--tag-color': meta.color }
      })
        .on('click', function () {
          // Если этот тип уже активен — снимаем (возврат к «Все»)
          if (activeFilters.has(t)) {
            activeFilters.clear();
          } else {
            activeFilters.clear();
            activeFilters.add(t);
          }
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

  // ── Статистика в шапке ────────────────────────────────────────────
  $('#stat-types').text(CARDS.length);
  $('#stat-total').text(CARDS.reduce(function (sum, c) { return sum + (c.qty || 1); }, 0));

  // ── Инициализация ─────────────────────────────────────────────────
  buildFilters();
  applyFilter();

});

$(function () {

  // ── Мета типов ────────────────────────────────────────────────────
  var TYPE_META = {
    action:       { label: 'Действие',      color: '#8a7040' },
    weapon:       { label: 'Оружие',        color: '#a03030' },
    trap:         { label: 'Ловушка',       color: '#7a3a8a' },
    character:    { label: 'Персонаж',      color: '#2a6a8a' },
    modifier:     { label: 'Модификатор',   color: '#3a6a3a' },
    defense:      { label: 'Защита',        color: '#2a5a7a' },
    stance:       { label: 'Стойка',        color: '#7a5a20' },
    effect:       { label: 'Эффект',        color: '#5a3a7a' },
    intervention: { label: 'Вмешательство', color: '#8a5020' },
    group:        { label: 'Групповая',     color: '#4a6a2a' }
  };

  var ALL_TYPES = Object.keys(TYPE_META);

  // ── Состояние фильтра ─────────────────────────────────────────────
  // activeFilters — Set активных типов; пусто = показывать все
  var activeFilters = new Set();

  // ── Утилиты ───────────────────────────────────────────────────────
  function pad(n) {
    return n < 10 ? '0' + n : '' + n;
  }

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
      $('<div>', { class: 'card-title-wrap' }).append(
        $('<span>', { class: 'card-title', text: card.title })
      ),

      // Слой 4: жёлтая плашка с описанием внизу
      $('<div>', { class: 'card-desc-wrap' }).append(
        $('<div>', { class: 'card-desc', text: card.desc })
      )
    );

    // Внешний контейнер: card + footer (типы слева, qty справа)
    var $footer = $('<div>', { class: 'card-footer' }).append(
      buildTypeTags(card.types),
      $('<div>', { class: 'card-qty', text: '×' + (card.qty || 1) })
    );

    var $item = $('<div>', { class: 'card-item ' + typeClasses, 'data-types': card.types.join(' ') }).append(
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

  // ── Фильтрация ────────────────────────────────────────────────────
  function applyFilter() {
    var total = 0;
    $('#grid .card-item').each(function () {
      var cardTypes = $(this).data('types').split(' ');
      var visible = activeFilters.size === 0 ||
        cardTypes.some(function (t) { return activeFilters.has(t); });
      $(this).toggleClass('card--hidden', !visible);
      if (visible) total++;
    });
    $('.count').text(total + ' карточек');

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

  // ── Рендер карточек ───────────────────────────────────────────────
  var $grid = $('#grid');

  $.each(CARDS, function (_, card) {
    $grid.append(buildCard(card));
  });

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

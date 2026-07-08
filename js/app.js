$(function () {

  // ── Мета типов ────────────────────────────────────────────────────
  var TYPE_META = {
    action:       { label: 'Действие',      color: '#FFDDDD' },
    weapon:       { label: 'Оружие',        color: '#ED1C24' },
    trap:         { label: 'Ловушка',       color: '#5f8598' },
    character:    { label: 'Персонаж',      color: '#ddd' },
    modifier:     { label: 'Модификатор',   color: '#ED1C24' },
    defense:      { label: 'Защита',        color: '#dca300' },
    stance:       { label: 'Стойка',        color: '#A78B6B' },
    effect:       { label: 'Эффект',        color: '#FFDDDD' },
    intervention: { label: 'Вмешательство', color: '#3B8476' },
    aoe:          { label: 'Групповая',     color: '#FFDDDD' },
    role:         { label: 'Роль',          color: '#9c6ec0' },
    aura:         { label: 'Аура',          color: '#93a32e' }
  };

  var ALL_TYPES = Object.keys(TYPE_META);

  // Типы, для которых показывается блок-метка над описанием
  var BLOCK_TYPES = ['trap', 'stance', 'modifier', 'intervention', 'defense', 'effect', 'aura'];

  // ── Цвета верхней плашки по группе ───────────────────────────────
  var GROUP_TITLE_COLOR = {
    defense:      '#dca300',
    trap:         '#43525A',
    weapon:       '#231F20',
    stance:       '#A78B6B',
    modifier:     '#ED1C24',
    aoe:          '#231F20',
    aura:     '#93a32e',
    effect:       '#231F20',
    intervention: '#3B8476',
    character:    '#ddd',
    role:         '#5d3c75',
    action:       '#231F20',
    trash:        '#3a3a3a'
  };

  // ── Порядок и названия групп ──────────────────────────────────────
  // role идёт первой — это мета-карта (кто играет), не часть колоды.
  var GROUP_ORDER = [
    'weapon', 'trap', 'defense', 'stance', 'modifier',
    'aoe', 'aura', 'effect', 'action', 'intervention',  'character', 'role',
  ];

  var GROUP_LABELS = {
    weapon:       'Оружие',
    trap:         'Ловушки',
    defense:      'Защита',
    stance:       'Стойки',
    modifier:     'Модификаторы',
    aoe:          'Групповые',
    effect:       'Эффекты',
    action:       'Действия',
    intervention: 'Вмешательства',
    role:         'Роли',
    aura:         'Аура',
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

  // ── Типографика ───────────────────────────────────────────────────

  // Экранирует HTML-спецсимволы в сыром тексте.
  function escapeHtml(text) {
    if (!text) return '';
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Применяет &nbsp; после коротких слов (1–2 буквы) к уже готовому
  // HTML: обходит теги и обрабатывает каждый текстовый узел отдельно,
  // благодаря чему текст после <br> и внутри <span> тоже покрывается.
  function typographHtml(html) {
    if (!html) return '';
    return html.replace(/(<[^>]+>)|([^<]+)/g, function (match, tag, text) {
      if (text) {
        return text.replace(/(\s|^)([А-ЯЁа-яёA-Za-z]{1,2}) /g, '$1$2&nbsp;');
      }
      return match; // тег оставляем как есть
    });
  }

  // Оставляем typograph для обратной совместимости (используется вне renderDescPart).
  function typograph(text) {
    return typographHtml(escapeHtml(text));
  }

  // ── Построение блока описания карточки ───────────────────────────
  // Если в desc встречается конструкция "-ИЛИ-" (с любыми пробелами
  // вокруг), описание разбивается на части, между которыми рисуется
  // компактный аналог .group-divider — горизонтальные линии и слово
  // «ИЛИ» по центру. CSS — в card.css.
  //
  // Дополнительно: каждая часть может начинаться с type-префикса
  // (UPPERCASE-русское слово, например ЛОВУШКА, ЗАЩИТА, МОДИФИКАТОР),
  // отделённого от остального текста ` | `. Префикс выделяется в
  // отдельный <span class="card-desc-prefix"> для стилизации (курсив).
  // Сам разделитель `|` в DOM не выводим — он только маркер в данных.
  //
  // Порядок обработки: escapeHtml → applyLabels → typographHtml,
  // чтобы &nbsp; применялся уже после вставки всех span и <br>.
  function renderDescPart(text) {
    var m = /^([А-ЯЁ][А-ЯЁ\s]*?)\s*\|\s+/.exec(text);
    if (m) {
      var prefix = escapeHtml(m[1].replace(/\s+/g, ' ').trim());
      var rest   = applyLabels(escapeHtml(text.slice(m[0].length)));
      return typographHtml('<span class="card-desc-prefix">' + prefix + '</span> ' + rest);
    }
    return typographHtml(applyLabels(escapeHtml(text)));
  }

  // Заменяет {текст} в уже типографированной HTML-строке на
  // <span class="card-desc-label card-desc-label-<kind>">текст</span>.
  // Kind определяется по корневому маркеру в тексте (регистронезависимо).
  var DESC_LABEL_KINDS = [
    { kind: 'samurai',   root: 'самур' },
    { kind: 'ninja',     root: 'ниндз'  },
    { kind: 'deathdoor', root: 'порог'  },
    { kind: 'deathrattle', root: 'смерт'  },
  ];

  function detectDescLabelKind(text) {
    var lower = text.toLowerCase();
    for (var i = 0; i < DESC_LABEL_KINDS.length; i++) {
      if (lower.indexOf(DESC_LABEL_KINDS[i].root) !== -1) {
        return DESC_LABEL_KINDS[i].kind;
      }
    }
    return null;
  }

  function applyLabels(html) {
    return html
      .replace(/\[NL\]/g, '<br>')
      .replace(/\{([^}]+)\}/g, function (_, inner) {
        var kind = detectDescLabelKind(inner);
        var cls = 'card-desc-label' + (kind ? ' card-desc-label-' + kind : '');
        return '<span class="' + cls + '">' + inner + '</span>';
      });
  }

  function buildDescContent(desc) {
    var parts = String(desc).split(/\s*-ИЛИ-\s*/)
      .map(function (p) { return p.replace(/^\s+|\s+$/g, ''); })
      .filter(function (p) { return p.length > 0; });

    if (parts.length <= 1) {
      return $('<div>', { class: 'card-desc' }).html(renderDescPart(desc));
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
        $('<div>', { class: 'card-desc-part' }).html(renderDescPart(part))
      );
    });
    return $wrap;
  }

  // ── Позиционирование yellow-плашки описания ─────────────────────
  // Плашка .card-desc-wrap встаёт впритык под нижним краем арта:
  // top задаётся в процентах, чтобы значение оставалось корректным
  // и на экране, и в печати (там та же карта, только шире).
  //
  // Функция устойчива к трём типичным гонкам:
  //   1. Layout ещё не устоялся (image load сработал до grid-reflow) →
  //      retry на requestAnimationFrame.
  //   2. Salma Pro ещё не подгружен → минимальная высота описания
  //      считается fallback-шрифтом и оказывается меньше реальной →
  //      верхний край плашки уезжает слишком низко → sanity-clamp
  //      удерживает результат в разумном диапазоне.
  //   3. Cached image — жёлтый .complete + naturalWidth > 0 после
  //      подписки на 'load' не всегда триггерит handler → руками
  //      вызываем positionDescWrap на всех картах после первого
  //      applyFilter() и повторно после document.fonts.ready.
  function positionDescWrap(imgEl) {
    if (!imgEl) return;
    var $img = $(imgEl);
    var $card = $img.closest('.card');
    var $wrap = $card.find('.card-desc-wrap');
    if (!$wrap.length) return;

    var cardH = $card[0].offsetHeight;
    var artH  = imgEl.offsetHeight;

    // Layout ещё не готов — попробуем на следующем кадре.
    if (cardH < 80 || artH < 40) {
      requestAnimationFrame(function () { positionDescWrap(imgEl); });
      return;
    }

    var artBottom = imgEl.offsetTop + artH;

    $wrap.css('top', '');
    var minH = $wrap[0].scrollHeight;

    var topPx  = Math.min(artBottom, cardH - minH);
    var topPct = (topPx / cardH * 100) - 2.5;

    // Sanity clamp: заголовок сидит на ~14% сверху, поэтому плашка
    // описания не может быть выше того, а очень низко (>82%) она
    // тоже быть не должна — там не остаётся места для текста.
    // Если расчёт вышел за эти границы — значит layout / шрифт
    // выдали нам мусор, показываем безопасный дефолт.
    if (!isFinite(topPct) || topPct < 30 || topPct > 82) {
      topPct = Math.min(82, Math.max(30, isFinite(topPct) ? topPct : 60));
    }

    $wrap.css('top', topPct.toFixed(3) + '%');

    var $iconsOr = $card.find('.card-icons-or');
    if ($iconsOr.length) {
      $iconsOr.css('bottom', (100 - topPct).toFixed(3) + '%');
    }
  }

  // Прогнать positionDescWrap по ВСЕМ card-art'ам, которые уже
  // загружены (в т. ч. cached, для которых 'load' мог сработать
  // до подписки), либо готовы к замеру. Используется:
  //   • сразу после первого applyFilter — на старте
  //   • после document.fonts.ready — если Salma Pro подъехал позже
  //   • на beforeprint — измеряем в контексте print media,
  //     чтобы страница гарантированно ушла с правильными top-ами
  function recomputeAllDescWraps() {
    $('#grid .card-art').each(function () {
      if (this.complete && this.naturalWidth > 0) {
        positionDescWrap(this);
      }
    });
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

      // Слой 0.5: overlay-фон для оружия с iconsOr — поверх weapon_bg,
      // но под card-art. Сигналит, что у оружия есть альтернативная
      // ветка использования (см. конструкцию "-ИЛИ-" в desc).
      // Если файла media/weapon_bg_or.png нет — img молча прячется.
      (card.group === 'weapon' && card.iconsOr && card.iconsOr.length)
        ? $('<img>', {
            class: 'card-bg-or',
            src: 'media/weapon_bg_or.png',
            alt: '',
            draggable: false
          }).on('error', function () { $(this).hide(); })
        : null,

      // Слой 1: арт (самый нижний).
      // Позиционирование yellow-плашки описания вычисляется через
      // positionDescWrap (см. определение ниже) — оно retry-safe:
      // если layout ещё не готов / шрифт не загрузился, откладывает
      // повторный замер до следующего кадра.
      $('<img>', { class: 'card-art', src: card.img, alt: card.title, loading: 'lazy' })
        .on('load', function () {
          positionDescWrap(this);
        }),

      // Слой 2: иконки из icons[] — вертикальный стек в левом верхнем углу арта
      card.icons && card.icons.length
        ? $('<div>', { class: 'card-icons' }).append(
            $.map(card.icons, function (icon) {
              return $('<img>', {
                class: 'card-icon card-icon-' + icon,
                src: 'media/' + icon + '.png',
                alt: icon,
                draggable: false
              });
            })
          )
        : null,

      // Слой 2b: иконки из iconsOr[] — зеркало icons по углу.
      // Вертикальный стек заякорен в правом нижнем углу карты:
      // ПОСЛЕДНИЙ элемент массива стоит в углу, первый — вверху стопки
      // (порядок в массиве не переворачиваем). Обычно используется
      // парно с конструкцией "-ИЛИ-" в desc: первая ветка описания
      // обозначается icons, альтернатива — iconsOr.
      card.iconsOr && card.iconsOr.length
        ? $('<div>', { class: 'card-icons-or' }).append(
            $.map(card.iconsOr, function (icon) {
              return $('<img>', {
                class: 'card-icon card-icon-' + icon,
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
      // Приоритет фона:
      //   1. card.titleBgColor (per-card override) — самый высокий
      //   2. для group=character ничего inline не ставим — паперовый
      //      фон задаёт CSS-правило .card-character .card-title-wrap
      //   3. иначе GROUP_TITLE_COLOR[group] || '#231F20'
      (function () {
        var titleBg = card.titleBgColor
                   || (card.group === 'character'
                         ? null
                         : (GROUP_TITLE_COLOR[card.group] || '#231F20'));
        var $tw = $('<div>', { class: 'card-title-wrap' });
        if (titleBg) $tw.css('background', titleBg);
        $tw.append(
          $('<span>', { class: 'card-title', text: card.title }),
          card.subtitle
            ? $('<span>', { class: 'card-subtitle', text: card.subtitle })
            : null
        );
        return $tw;
      })(),

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
      card.desc ? (function () {
        var blockLabels = card.types
          .filter(function (t) { return BLOCK_TYPES.indexOf(t) !== -1; })
          .map(function (t) { return (TYPE_META[t] || {}).label || t; });

        var $descContent = buildDescContent(card.desc);

        if (blockLabels.length) {
          var $span = $('<span>', { class: 'card-block-types', text: blockLabels.join(' · ') + ' ·' });
          var $target = $descContent.hasClass('card-desc--split')
            ? $descContent.find('.card-desc-part').first()
            : $descContent;
          $target.prepend($span);
        }

        return $('<div>', { class: 'card-desc-wrap' }).append(
          $('<img>', { class: 'card-delimiter', src: 'media/delimiter.png', alt: '', draggable: false }),
          $descContent
        );
      })() : null
    );

    // Кнопка «поделиться» — видна только когда карта в зуме (CSS),
    // ставит location.hash = card-<ID> и копирует полный URL в буфер.
    // По этому хешу страница автоматически зумирует карту при загрузке
    // (см. zoomCardById ниже). Кладём её в .card-footer перед местом,
    // куда comments.js append'ит .card-comments-btn — получается
    // последовательность qty → share → comment.
    var $shareBtn = $('<button>', {
      type: 'button',
      class: 'card-share-btn',
      title: 'Скопировать ссылку на карту',
      html: '\u{1F517}'  // 🔗
    }).on('click', function (e) {
      e.stopPropagation();
      e.preventDefault();
      var hash = 'card-' + card.id;
      // Embed-URL — для вставки в iframe: показывает только эту карту
      // на белом фоне. Обычный hash-URL обновляем для навигации внутри
      // приложения (зум при перезагрузке), но в буфер кладём embed.
      var embedUrl = window.location.origin + window.location.pathname +
                     '?embed=' + card.id;
      if (location.hash !== '#' + hash) {
        location.hash = hash;
      }

      var $btn = $(this);
      var orig = $btn.html();
      function flash(sym, modCls) {
        $btn.html(sym)
            .removeClass('card-share-btn--ok card-share-btn--err')
            .addClass(modCls);
        setTimeout(function () {
          $btn.html(orig).removeClass('card-share-btn--ok card-share-btn--err');
        }, 1500);
      }

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(embedUrl).then(
          function () { flash('✓', 'card-share-btn--ok'); },
          function () { flash('✗', 'card-share-btn--err'); }
        );
      } else {
        // Fallback для контекстов без Clipboard API (file://, старые браузеры)
        window.prompt('Скопируйте ссылку:', embedUrl);
      }
    }).on('mousedown', function (e) { e.stopPropagation(); });

    // Внешний контейнер: card + footer (типы слева, qty + share + comment справа).
    // share-кнопка появляется здесь сразу; .card-comments-btn будет
    // добавлен позже модулем comments.js — таким образом получаем
    // нужный порядок: ... qty | share | comment.
    var $footer = $('<div>', { class: 'card-footer' }).append(
      buildTypeTags(card.types, card.tags || []),
      $('<div>', { class: 'card-qty', text: '×' + (card.qty || 1) }),
      $shareBtn
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
      'data-tags': (card.tags || []).join(' '),
      'data-icons': (card.icons || []).join(' '),
      'data-has-todo': ((card.desc || '').toLowerCase().indexOf('todo') !== -1 ||
                        (card.img  || '').indexOf('card_todo.png') !== -1) ? '1' : null
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
      var isTrash = (card.tags || []).indexOf('trash') !== -1;
      if (isTrash) {
        $item.attr('data-trash-real', '1').addClass('card--hidden');
      }
      $grid.append($item);

      // Клоны для режима «Печать количеством»: qty-1 копий, всегда скрыты на экране.
      if (!isTrash) {
        var qty = card.qty || 1;
        for (var q = 1; q < qty; q++) {
          $grid.append(
            $item.clone(false)
              .addClass('card-print-clone card--hidden')
              .removeAttr('id')
          );
        }
      }
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
    var trashTypes = 0;
    var visibleByGroup = {};
    var isTrashMode = activeMode === '__trash__';

    $('#grid .card-item').each(function () {
      var $el       = $(this);
      if ($el.hasClass('card-print-clone')) return; // клоны управляются отдельно
      var isReal    = !!$el.attr('data-trash-real');
      var isPseudo  = !!$el.attr('data-trash-pseudo');
      var cardTypes = $el.data('types').split(' ');
      var cardTags  = ($el.data('tags')  || '').toString().split(' ');
      var cardIcons = ($el.data('icons') || '').toString().split(' ');

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
          visible = cardTags.indexOf('draft') !== -1 ||
                    $el.attr('data-has-todo') === '1';
        } else if (activeMode === '__comments__') {
          visible = $el.attr('data-has-comments') === '1';
        } else if (activeMode === '__rolectx__') {
          visible = cardIcons.indexOf('rolectx') !== -1;
        } else if (activeMode === '__hpctx__') {
          visible = cardIcons.indexOf('hpctx') !== -1;
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
          visible = cardTags.indexOf('draft') !== -1 ||
                    $el.attr('data-has-todo') === '1';
        } else if (activeMode === '__comments__') {
          // data-has-comments проставляется в comments.js после
          // bucket.list: '1' если у карточки есть комментарии, иначе атрибут
          // отсутствует. Если comments-модуль не загружен, фильтр пуст.
          visible = $el.attr('data-has-comments') === '1';
        } else if (activeMode === '__rolectx__') {
          visible = cardIcons.indexOf('rolectx') !== -1;
        } else if (activeMode === '__hpctx__') {
          visible = cardIcons.indexOf('hpctx') !== -1;
        } else if (activeMode) {
          visible = cardTypes.indexOf(activeMode) !== -1;
        } else {
          visible = true;
        }
      }

      $el.toggleClass('card--hidden', !visible);
      if (visible) {
        if (isPseudo) {
          trashTypes++;
        } else {
          totalTypes++;
          totalQty += parseInt($el.data('qty'), 10) || 1;
        }
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

    var countText = isTrashMode
      ? totalTypes + ' видов · ' + totalQty + ' карт'
      : totalTypes + ' видов · ' + totalQty + ' карт' +
        (trashTypes > 0 ? ' · 🗑 ' + trashTypes + ' в корзине' : '');
    $('.count').text(countText);

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
  var VALID_MODES = ALL_TYPES.concat(['__poison__', '__print__', '__draft__', '__trash__', '__comments__', '__rolectx__', '__hpctx__']);

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

    $('<button>', { class: 'filter-btn filter-btn--rolectx', text: '⚔ Клановые', 'data-type': '__rolectx__' })
      .on('click', function () {
        setFilter(activeMode === '__rolectx__' ? null : '__rolectx__');
      })
      .appendTo($row3);

    $('<button>', { class: 'filter-btn filter-btn--hpctx', text: '❤ Low/Full HP', 'data-type': '__hpctx__' })
      .on('click', function () {
        setFilter(activeMode === '__hpctx__' ? null : '__hpctx__');
      })
      .appendTo($row3);

    // ── Ряд 4: опции печати ──────────────────────────────────────────
    var $row4 = $('<div>', { class: 'filter-row filter-row--print-options' }).appendTo($bar);
    var $cb = $('<input>', { type: 'checkbox', id: 'print-qty-checkbox', class: 'print-qty-checkbox' });
    $cb.on('change', function () {
      document.body.classList.toggle('print-qty-mode', this.checked);
    });
    $('<label>', { class: 'print-qty-label', 'for': 'print-qty-checkbox' })
      .append($cb, $('<span>', { text: ' Печать количеством (Quantity Based Print)' }))
      .appendTo($row4);

    // Чекбокс «Печать рубашек» — после каждой страницы фронтов
    // wrapForPrint вставляет страницу с рубашками (см. ниже).
    var $backsCb = $('<input>', {
      type: 'checkbox',
      id:   'print-backs-checkbox',
      class: 'print-backs-checkbox'
    });
    $backsCb.on('change', function () {
      document.body.classList.toggle('print-backs-mode', this.checked);
    });
    $('<label>', {
      class: 'print-backs-label',
      'for': 'print-backs-checkbox',
      title: 'После каждых 9 карточек добавляет страницу с рубашками для duplex-печати'
    })
      .append($backsCb, $('<span>', { text: ' Печать рубашек' }))
      .appendTo($row4);

    // ── CMYK soft-proof через Fogra39 ICC ──────────────────────────
    // Тоггл подгружает styles/proof-cmyk-baked.css и тоглит
    // body.proof-cmyk-baked. Логика сидит в инлайн-скрипте app.html
    // (window.CmykProof.{on,off,toggle}); тут только UI.
    var $cmykCb = $('<input>', {
      type:  'checkbox',
      id:    'cmyk-proof-checkbox',
      class: 'cmyk-proof-checkbox'
    });
    $cmykCb.on('change', function () {
      if (window.CmykProof) window.CmykProof.toggle();
    });
    $('<label>', {
      class: 'cmyk-proof-label',
      'for': 'cmyk-proof-checkbox',
      title: 'Превью с эмуляцией офсетной печати (Fogra39 ICC)'
    }).append(
      $cmykCb,
      $('<span>', { text: ' 🎨 CMYK preview (Fogra39)' })
    ).appendTo($row4);

    // Синхронизация чекбокса с реальным состоянием:
    //   • при загрузке (если ?proof=cmyk был в URL — head-скрипт
    //     уже включил его до того, как мы построили UI)
    //   • при будущих изменениях через head-скрипт / URL
    function syncCmykCheckbox() {
      $cmykCb.prop('checked',
        !!(window.CmykProof && window.CmykProof.isOn()));
    }
    syncCmykCheckbox();
    document.addEventListener('cmyk-proof-change', syncCmykCheckbox);
  }

  // ── Закрытие зума кликом вне карточки или Escape ──────────────────
  $(document).on('click', function () {
    $('.card-item.is-zoomed').removeClass('is-zoomed');
  });
  $(document).on('keydown', function (e) {
    if (e.key === 'Escape') $('.card-item.is-zoomed').removeClass('is-zoomed');
  });

  // ── Статистика в шапке (общая, не зависит от фильтра) ───────────
  // activeCards — база для sidebar-статистики: без корзины и без черновиков.
  var activeCards = CARDS.filter(function (c) {
    return (c.tags || []).indexOf('trash') === -1;
  });

  // Блок .stats в шапке: все карты кроме корзины (черновики входят).
  var nonTrashCards = CARDS.filter(function (c) {
    return (c.tags || []).indexOf('trash') === -1;
  });
  $('#stat-types').text(nonTrashCards.length);
  $('#stat-total').text(nonTrashCards.reduce(function (sum, c) { return sum + (c.qty || 1); }, 0));

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

    // Корзина в summary — только типов (qty не важна)
    var trashAll = CARDS.filter(function (c) { return (c.tags || []).indexOf('trash') !== -1; });
    $('#stat-trash-types').text(trashAll.length);

    // Считаем по группам — все карты кроме trash
    var groupStats = {};
    $.each(CARDS, function (_, card) {
      if ((card.tags || []).indexOf('trash') !== -1) return;
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

    // Корзина — только в stats-summary (см. ниже), не в таблице
    var trashCards = CARDS.filter(function (c) { return (c.tags || []).indexOf('trash') !== -1; });

    // Псевдо-тег Draft — одна суммарная строка
    var draftCards = CARDS.filter(function (c) { return (c.tags || []).indexOf('draft') !== -1; });
    if (draftCards.length) {
      $('<tr>', { class: 'stats-row--pseudo' }).append(
        $('<td>', { text: '✏ Черновик' }),
        $('<td>', { text: draftCards.length }),
        $('<td>', { text: draftCards.reduce(function (s, c) { return s + (c.qty || 1); }, 0) }),
        $('<td>', { text: '—' })
      ).appendTo($tbody);
    }

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
    var isQtyMode = document.body.classList.contains('print-qty-mode');

    if (isQtyMode) {
      // Открываем клоны для видимых не-trash карт, чтобы они попали
      // в выборку и разложились по print-page вместе с оригиналами.
      $('#grid .card-item:not(.card--hidden):not([data-trash-real]):not([data-trash-pseudo]):not(.card-print-clone)')
        .each(function () {
          var cardId = $(this).data('card-id');
          $('#grid .card-print-clone[data-card-id="' + cardId + '"]')
            .removeClass('card--hidden');
        });
    }

    // Карточки с тегом trash никогда не попадают в печатную версию —
    // ни real-копии в родных группах, ни pseudo-копии в Корзине.
    var $cards = $('#grid .card-item:not(.card--hidden)').filter(function () {
      var tags = ($(this).attr('data-tags') || '').split(/\s+/);
      return tags.indexOf('trash') === -1;
    });
    var pages = [];
    for (var i = 0; i < $cards.length; i += 9) {
      pages.push($cards.slice(i, i + 9));
    }
    $.each(pages, function (_, $group) {
      $group.wrapAll('<div class="print-page"></div>');
    });

    // Перед тем как принтер сделает первый layout-pass в @media print,
    // принудительно снимаем lazy у всех card-art (иначе они грузятся
    // прямо в процессе print flow'а и мешают замерам).
    $('#grid .card-art[loading="lazy"]').removeAttr('loading');

    // На печати НЕ полагаемся на JS-computed top% для .card-desc-wrap
    // и bottom% для .card-icons-or — эта эвристика собрана под screen-
    // layout, а при переходе в @media print у нас есть три разъезжающих
    // фактора: (а) шрифт может рендериться другой — фаллбэк отличается,
    // (б) offsetHeight у cached-lazy картинок иногда возвращает мусор,
    // (в) natural aspect картинки vs 611/978 карты часто не совпадают
    // и плашка «схлопывается» до нескольких миллиметров.
    // Сбрасываем inline и отдаём позиционирование чистому CSS:
    // .card-desc-wrap { bottom: 0 } + height=fit-content — плашка
    // всегда встаёт снизу, натуральной высотой под свой текст. Иконки
    // iconsOr возвращаются в дефолтные 14% от низа карты. Это гарантирует,
    // что описание никогда не обрезается и не переполняется на бумаге.
    $('#grid .card-desc-wrap').css('top', '');
    $('#grid .card-icons-or').css('bottom', '');

    // ── Печать рубашек ──
    // Если включён режим, после каждой страницы фронтов вставляем
    // зеркальную страницу-рубашку: те же 9 позиций в той же сетке,
    // но каждая карта заменена на media/backs/{group}.png.
    // Двусторонняя печать с duplex-flip укладывает их корректно.
    if (document.body.classList.contains('print-backs-mode')) {
      $('.print-page').each(function () {
        var $frontPage = $(this);
        var $backPage = $('<div>', { class: 'print-page print-page--back' });
        $frontPage.children('.card-item').each(function () {
          var group = $(this).attr('data-group');
          var img = (group === 'role')      ? 'media/backs/role.png'
                  : (group === 'character') ? 'media/backs/character.png'
                  :                            'media/backs/default.png';
          $('<div>', { class: 'card-item card-item--back' })
            .append($('<img>', {
              class: 'card-back-img',
              src: img,
              alt: '',
              draggable: false
            }).on('error', function () { $(this).hide(); }))
            .appendTo($backPage);
        });
        $frontPage.after($backPage);
      });
    }
  }

  function unwrapAfterPrint() {
    // Синтетические страницы-рубашки — выкидываем целиком, иначе при
    // повторной печати они задвоятся.
    $('.print-page--back').remove();
    // Возвращаем qty-клоны в скрытое состояние
    $('#grid .card-print-clone').addClass('card--hidden');
    $('.print-page').each(function () {
      $(this).replaceWith($(this).children());
    });
    // На экране мы хотим красивое JS-позиционирование yellow-плашки
    // вплотную к нижнему краю арта — восстанавливаем его после того,
    // как print-flow завершился и inline-стили были сброшены выше.
    recomputeAllDescWraps();
  }

  window.addEventListener('beforeprint', wrapForPrint);
  window.addEventListener('afterprint', unwrapAfterPrint);

  // ── Hash-роутинг для одиночной карты ─────────────────────────────
  // Формат хеша: #card-<ID>. По нему страница автоматически зумирует
  // карту (см. кнопку «поделиться» в zoom-режиме). Хеши вида
  // VALID_MODES обрабатываются отдельно как фильтр (см. ниже).
  function zoomCardById(cardId) {
    if (cardId == null) return;
    // Предпочитаем настоящую карту из её родной группы; pseudo-копия
    // в Корзине — запасной вариант на случай если real-копии нет.
    var $target = $('#grid .card-item[data-card-id="' + cardId + '"]:not([data-trash-pseudo]):not(.card-print-clone)').first();
    if (!$target.length) {
      $target = $('#grid .card-item[data-card-id="' + cardId + '"]:not(.card-print-clone)').first();
    }
    if (!$target.length) return;

    // Если карта скрыта активным фильтром — снимаем фильтр.
    if ($target.hasClass('card--hidden')) {
      setFilter(null);
    }

    // Закрываем все остальные зумы и открываем нужный.
    $('.card-item.is-zoomed').not($target).removeClass('is-zoomed');
    $target.addClass('is-zoomed');

    // Прокручиваем карту в видимую область.
    setTimeout(function () {
      if ($target[0].scrollIntoView) {
        $target[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 50);
  }

  function applyCardHashIfAny() {
    var m = /^card-(\d+)$/.exec(location.hash.replace(/^#/, ''));
    if (m) zoomCardById(m[1]);
  }

  // Если кто-то меняет hash вручную / через back-forward / через
  // клик по другой share-ссылке — переоткрываем нужную карту.
  $(window).on('hashchange', applyCardHashIfAny);

  // ── Динамические свойства карт ────────────────────────────────────
  // hasRoleContext: true когда в icons есть 'rolectx'
  // hasHpCtx:      true когда в icons есть 'hpctx'
  CARDS.forEach(function (card) {
    Object.defineProperty(card, 'hasRoleContext', {
      get: function () { return (this.icons || []).indexOf('rolectx') !== -1; },
      enumerable: false,
      configurable: true
    });
    Object.defineProperty(card, 'hasHpCtx', {
      get: function () { return (this.icons || []).indexOf('hpctx') !== -1; },
      enumerable: false,
      configurable: true
    });
    Object.defineProperty(card, 'hasTodo', {
      get: function () {
        return (this.desc || '').toLowerCase().indexOf('todo') !== -1 ||
               (this.img  || '').indexOf('card_todo.png') !== -1;
      },
      enumerable: false,
      configurable: true
    });
  });

  // ── Инициализация ─────────────────────────────────────────────────
  buildFilters();
  buildStats();

  // Восстанавливаем фильтр из hash (если он валидный режим)
  var hashMode = location.hash.replace(/^#/, '');
  if (hashMode && VALID_MODES.indexOf(hashMode) !== -1) {
    activeMode = hashMode;
  }
  applyFilter();

  // Hash вида card-<ID> — зумим карту после применения фильтра.
  applyCardHashIfAny();

  // Одноразовые пересчёты позиции yellow-плашки описания:
  //   1. следующий кадр после первого layout — на случай, если
  //      cached-image'ам браузер не отправил 'load' после подписки;
  //   2. document.fonts.ready — Salma Pro / Han Zi могут подгрузиться
  //      уже после первого замера, и scrollHeight у desc окажется
  //      меньше реальной высоты. После загрузки шрифтов пересчитываем
  //      и подгоняем верхний край плашки заново.
  requestAnimationFrame(recomputeAllDescWraps);
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(recomputeAllDescWraps);
  }

  // ── Embed-режим: ?embed=<ID> ──────────────────────────────────────
  // Скрывает весь UI и показывает одну карту на белом фоне —
  // удобно для вставки в <iframe> на других страницах.
  var embedId = (new URLSearchParams(window.location.search)).get('embed');
  if (embedId) {
    document.body.classList.add('embed-mode');
    $('#grid .card-item').each(function () {
      var $el = $(this);
      if (String($el.data('card-id')) !== String(embedId)) {
        $el.addClass('card--hidden');
      } else {
        $el.removeClass('card--hidden');
      }
    });
    $('[data-group-divider]').addClass('group-divider--hidden');
  }

});

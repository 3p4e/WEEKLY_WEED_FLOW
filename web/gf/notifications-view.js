/* notifications-view.js — per-user Inbox + shared Activity feed.
   Design: docs/RESEARCH-NOTIFICATIONS-2026-07.md (Linear/GitHub/Asana model:
   always-on inbox, reason labels, unread → read → done lifecycle, feed as the
   separate awareness surface). Bilingual by structure: the backend stores
   verb + structured params; the sentence is rendered HERE per GF.state.lang.
   Delivery: 75s polling + refresh on tab focus; the unread count comes from
   the server (single source of truth for the bell badge). */
window.GF = window.GF || {}; GF.WWF = GF.WWF || {};

(function () {
  GF.WWF._notif = { items: [], feed: [], tab: 'inbox', filter: '', unread: 0, loaded: false,
                    moreItems: false, moreFeed: false,
                    // Last user this inbox was loaded for — a login as someone
                    // else must reset the module state, never show their items.
                    user: null,
                    // Team digest (GET /notifications/digest) — lazy: nothing is
                    // fetched until the panel is first opened.
                    digest: null, digestWindow: 'daily', digestOpen: false, digestLoading: false,
                    // id -> expiry ms: a notification just marked done/read locally,
                    // guarding against a 75s-poll GET that was already in flight
                    // (started before the action's own write landed) resurrecting
                    // it as undone/unread when it resolves a moment later.
                    _justDone: {}, _justRead: {} };
  const PAGE = 50;   // backend default limit on /notifications and /activity

  const who = (id) => (GF.PEOPLE && GF.PEOPLE[id] && GF.PEOPLE[id].name) || AL('Someone', 'Некој');

  // Object-type nouns for the generic line below — the backend's object_type
  // enum as a person would say it. An unknown type prints as itself.
  const OBJ = {
    task: { en: 'task', mk: 'задача' }, plant_batch: { en: 'batch', mk: 'серија' },
    qc_sample: { en: 'sample', mk: 'примерок' }, qc_certificate: { en: 'certificate', mk: 'сертификат' },
    qc_coq: { en: 'CoQ', mk: 'CoQ' }, qc_coa_document: { en: 'CoA document', mk: 'CoA документ' },
    qc_specification: { en: 'specification', mk: 'спецификација' }, qc_product: { en: 'product', mk: 'производ' },
    qc_potency_spec: { en: 'potency ladder', mk: 'скала на потентност' }, qc_oos: { en: 'OOS', mk: 'OOS' },
    decon_room_cycle: { en: 'decon cycle', mk: 'циклус на деконтаминација' }, decon_swab: { en: 'swab', mk: 'брис' },
    room: { en: 'room', mk: 'соба' }, waste_manifest: { en: 'waste manifest', mk: 'манифест за отпад' },
    biosecurity_event: { en: 'biosecurity check', mk: 'биобезбедносна проверка' },
    mother_plant: { en: 'mother plant', mk: 'мајка растение' }, selection_campaign: { en: 'campaign', mk: 'кампања' },
    harvest: { en: 'harvest', mk: 'жетва' }, ipm_application: { en: 'IPM application', mk: 'IPM третман' },
    irrigation_event: { en: 'feeding', mk: 'наводнување' }, trichome_check: { en: 'trichome check', mk: 'проверка на трихоми' },
    report_document: { en: 'weekly document', mk: 'неделен документ' }, facility_room: { en: 'room', mk: 'соба' },
  };
  const objNoun = (n) => { const o = OBJ[n.object_type]; return o ? AL(o.en, o.mk) : (n.object_type || ''); };
  const HO_ST = {
    accepted: { en: 'accepted', mk: 'прифати' }, rejected: { en: 'rejected', mk: 'одби' },
    cancelled: { en: 'cancelled', mk: 'откажа' },
  };

  // The pieces every batch sentence shares, each tolerant of an absent key.
  const batchBits = (p) => ({
    code: p.code ? `${p.code} — ` : '',
    count: p.plant_count != null ? String(p.plant_count) : '?',
    strain: p.strain || p.cultivar || p.product_code || AL('batch', 'серија'),
    room: p.room || p.room_name || '',
    phase: p.phase ? ` (${p.phase})` : '',
  });

  // verb + params → sentence, per current language. Structured params only.
  // Every verb the backend emits (grep 'verb="' over backend/app) has a
  // sentence here; anything new falls to the generic line, which still
  // names the actor, the object and the action in both languages rather
  // than printing a raw machine word (review 2026-09-27, FE-18).
  const sentence = (n) => {
    const p = n.params || {}, a = who(n.actor_id), t = p.title || '';
    switch (n.verb) {
      case 'handoff':        return AL(`${a} proposed a handoff to ${p.to_dept}: ${t}`,
                                       `${a} предложи префрлање до ${p.to_dept}: ${t}`);
      case 'handoff_resolved': {
        const s = HO_ST[p.status] || { en: p.status, mk: p.status };
        return AL(`${a} ${s.en} the handoff: ${t}`, `${a} го ${s.mk} префрлањето: ${t}`);
      }
      case 'oos_opened':     return AL(`${a} opened ${p.oos_number} on batch ${p.batch_id}`,
                                       `${a} отвори ${p.oos_number} за серија ${p.batch_id}`);
      case 'qc_deviation':   return AL(`QC deviation (${p.reason}) on batch ${p.batch_id}`,
                                       `КК отстапување (${p.reason}) за серија ${p.batch_id}`);
      case 'decon_swab_positive': return AL(`Positive swab ${p.swab_code} in ${p.room}`,
                                            `Позитивен брис ${p.swab_code} во ${p.room}`);
      case 'decon_cycle_started': return AL(`${a} started a decon cycle in ${p.room} (${p.campaign})`,
                                            `${a} започна циклус на деконтаминација во ${p.room} (${p.campaign})`);
      case 'decon_room_released': return AL(`${a} released ${p.room} (${p.campaign})`,
                                            `${a} ја ослободи ${p.room} (${p.campaign})`);
      case 'decon_cycle_failed': return AL(`${a} failed the decon cycle in ${p.room}: ${p.reason}`,
                                           `${a} го означи циклусот во ${p.room} како неуспешен: ${p.reason}`);
      case 'decon_bleach_below_spec':
      case 'decon_tool_below_spec':
      case 'decon_corridor_below_spec':
                             return AL(`${p.ppm} ppm below specification in ${p.room}`,
                                       `${p.ppm} ppm под спецификација во ${p.room}`);
      case 'biosecurity_logged': return AL(`Biosecurity ${p.kind}: ${p.result}${p.room_name ? ' — ' + p.room_name : ''}`,
                                           `Биобезбедност ${p.kind}: ${p.result}${p.room_name ? ' — ' + p.room_name : ''}`);
      case 'mother_registered': return AL(`${a} registered mother ${p.code} (${p.product_code})`,
                                          `${a} регистрираше мајка ${p.code} (${p.product_code})`);
      case 'campaign_started': return AL(`${a} started selection campaign S${p.seq} (${p.material})`,
                                         `${a} започна кампања за селекција S${p.seq} (${p.material})`);
      case 'harvest_recorded': return AL(`${a} recorded harvest ${p.lot_code} from ${p.batch}`,
                                         `${a} запиша жетва ${p.lot_code} од ${p.batch}`);
      case 'harvest_dried':    return AL(`${p.lot_code} dried: ${p.dry_total_g} g`, `${p.lot_code} исушено: ${p.dry_total_g} g`);
      case 'harvest_closed':   return AL(`${a} closed lot ${p.lot_code}`, `${a} ја затвори серијата ${p.lot_code}`);
      case 'ipm_applied':      return AL(`${a} applied ${p.product} (${p.category})`, `${a} примени ${p.product} (${p.category})`);
      case 'trichome_checked': return AL(`${a}: trichome check on ${p.batch} — ${p.verdict}`,
                                         `${a}: проверка на трихоми за ${p.batch} — ${p.verdict}`);
      case 'trichome_corrected': return AL(`${a} corrected the trichome check on ${p.batch} (${(p.fields || []).join(', ')})`,
                                           `${a} ја поправи проверката на трихоми за ${p.batch} (${(p.fields || []).join(', ')})`);
      case 'irrigation_logged': return AL(`${a} logged feeding in ${p.room_name} (${p.method})`,
                                          `${a} запиша наводнување во ${p.room_name} (${p.method})`);
      case 'waste_manifest_sealed':    return AL(`${a} sealed waste manifest ${p.code}`, `${a} го затвори манифестот ${p.code}`);
      case 'waste_manifest_witnessed': return AL(`${a} witnessed waste manifest ${p.code}`, `${a} го потврди манифестот ${p.code}`);
      case 'waste_manifest_disposed':  return AL(`${a} disposed waste manifest ${p.code}${p.carrier_ref ? ' (' + p.carrier_ref + ')' : ''}`,
                                                 `${a} го уништи манифестот ${p.code}${p.carrier_ref ? ' (' + p.carrier_ref + ')' : ''}`);
      case 'sample_collected':   return AL(`${a} collected sample ${p.sample_id} (${p.batch_id})`,
                                           `${a} зеде примерок ${p.sample_id} (${p.batch_id})`);
      case 'sample_quarantined': return AL(`Sample quarantined — ${p.test_name}`, `Примерок во карантин — ${p.test_name}`);
      case 'spec_created':       return AL(`${a} created specification ${p.spec_id} (${p.material_code})`,
                                           `${a} креираше спецификација ${p.spec_id} (${p.material_code})`);
      case 'coa_signed':         return AL(`${a} signed a certificate (${p.meaning})`, `${a} потпиша сертификат (${p.meaning})`);
      case 'coa_verified':       return AL(`${a} verified a certificate: ${p.verdict} (${p.mismatches}/${p.checked} mismatches)`,
                                           `${a} провери сертификат: ${p.verdict} (${p.mismatches}/${p.checked} отстапувања)`);
      case 'coa_original_stored': return AL(`${a} stored the original ${p.filename}`, `${a} го зачува оригиналот ${p.filename}`);
      case 'ecoa_promoted':      return AL(`${a} promoted ${p.doc_number} to ${p.coa_number}`, `${a} го промовираше ${p.doc_number} во ${p.coa_number}`);
      case 'coq_compiled':       return AL(`${a} compiled ${p.coq_number} for batch ${p.batch_id}`, `${a} состави ${p.coq_number} за серија ${p.batch_id}`);
      case 'coq_reviewed':       return AL(`${a} reviewed ${p.coq_number}`, `${a} прегледа ${p.coq_number}`);
      case 'coq_rendered':       return AL(`${a} rendered ${p.coq_number}`, `${a} генерираше ${p.coq_number}`);
      case 'coq_generated':      return AL(`${a} generated the CoQ for ${p.coa_number}`, `${a} генерираше CoQ за ${p.coa_number}`);
      case 'coq_voided':         return AL(`${a} voided ${p.coq_number}: ${p.reason}`, `${a} поништи ${p.coq_number}: ${p.reason}`);
      case 'potency_spec_created':  return AL(`${a} created potency ladder v${p.version}`, `${a} креираше скала на потентност v${p.version}`);
      case 'potency_spec_approved': return AL(`${a} approved potency ladder v${p.version}`, `${a} одобри скала на потентност v${p.version}`);
      case 'facility_room_classified': return AL(`${a} classified room ${p.code}`, `${a} ја класифицираше собата ${p.code}`);
      case 'workflow_submit':  return AL(`${a} submitted for sign-off: ${t}`, `${a} поднесе за одобрување: ${t}`);
      case 'workflow_approve': return AL(`${a} approved: ${t}`, `${a} одобри: ${t}`);
      case 'workflow_reject':  return AL(`${a} rejected: ${t}`, `${a} одби: ${t}`);
      case 'workflow_block':   return AL(`${a} placed a QP block: ${t}`, `${a} стави QP блок: ${t}`);
      case 'workflow_unblock': return AL(`${a} lifted the QP block: ${t}`, `${a} го тргна QP блокот: ${t}`);
      case 'assigned':       return AL(`${a} assigned you: ${t}`, `${a} ви додели: ${t}`);
      case 'commented':      return AL(`${a} commented on: ${t}`, `${a} коментираше на: ${t}`)
                                   + (p.preview ? ` — “${p.preview}”` : '');
      case 'ack':            return p.accepted
                                   ? AL(`${a} accepted: ${t}`, `${a} прифати: ${t}`)
                                   : AL(`${a} declined: ${t}`, `${a} одби: ${t}`);
      case 'status_changed': {
        // Backend status enum → GF status key → localized label; statusLabel
        // is language-aware, so the one expression serves both branches (the
        // MK sentence used to print the raw English enum).
        const sl = GF.statusLabel
          ? GF.statusLabel(({ pending: 'pending', ongoing: 'working', completed: 'done' })[p.new] || p.new)
          : p.new;
        return AL(`${a}: ${t} → ${sl}`, `${a}: ${t} → ${sl}`);
      }
      case 'report_locked':  return AL(`${a} locked the weekly ${p.kind} (${p.week_start})`,
                                       `${a} го заклучи неделниот ${p.kind === 'plan' ? 'план' : 'извештај'} (${p.week_start})`);
      case 'created':        return AL(`${a} created: ${t}`, `${a} креираше: ${t}`);
      case 'unassigned':     return AL(`${a} unassigned you from: ${t}`, `${a} ве отстрани од: ${t}`);
      case 'due_soon':       return AL(`Due today: ${t}`, `Рок денес: ${t}`);
      case 'overdue':        return AL(`Overdue (${p.due}): ${t}`, `Задоцнето (${p.due}): ${t}`);
      // Batch registration / phase move (cultivation.py). The contract is
      // `code`, `strain` (cultivar NAME), `room` (room NAME), `plant_count`,
      // `phase`, and `old_room` / `old_phase` on a move; older events carry
      // `cultivar` and no room, so every key falls back and nothing prints
      // "undefined" (review 2026-09-27, R2-FE-04 / INV-02).
      case 'batch_added': {
        const b = batchBits(p);
        return AL(`${a} registered ${b.code}${b.count} × ${b.strain}${b.room ? ' in ' + b.room : ''}${b.phase}`,
                  `${a} регистрираше ${b.code}${b.count} × ${b.strain}${b.room ? ' во ' + b.room : ''}${b.phase}`);
      }
      case 'clone_run_started': return AL(`${a} started a clone run: ${p.cultivar} · ${p.planned_count} cuttings from ${p.mothers} mothers (${p.started_on})`,
                                          `${a} започна клонирање: ${p.cultivar} · ${p.planned_count} резници од ${p.mothers} мајки (${p.started_on})`);
      case 'batch_moved': {
        const b = batchBits(p);
        // "old room (old phase) → room (phase)"; whichever side has no room
        // prints its phase alone, and a phase-only move prints "clone → veg".
        const side = (room, phase) => room && phase ? `${room} (${phase})` : (room || phase || '');
        const from = side(p.old_room, p.old_phase), to = side(p.room, p.phase);
        const hop = from || to ? `: ${from || '?'} → ${to || '?'}` : '';
        return AL(`${a} moved ${b.code}${b.count} × ${b.strain}${hop}`,
                  `${a} премести ${b.code}${b.count} × ${b.strain}${hop}`);
      }
      // The product catalogue (qc/products.py) and the owner's out-of-grade
      // rule of 2026-09-06: a Total Δ9-THC outside the certified product's
      // window is handed to Cultivation and Production as a deviation.
      case 'potency_deviation': {
        const w = (p.window_min != null && p.window_max != null) ? ` (${p.window_min}–${p.window_max} %)` : '';
        const fall = p.regrade_to
          ? AL(` — the lot falls to ${p.regrade_to}`, ` — серијата паѓа на ${p.regrade_to}`)
          : AL(' — no grade of the strain holds it', ' — ниту една класа на сортата не ја содржи');
        return AL(`Potency deviation on batch ${p.batch_id}: Total Δ9-THC ${p.total_d9_thc} % is outside ${p.product_code}${w}${fall}; a formal OOS is required on the batch disposition (${p.coq_number})`,
                  `Отстапување на јачина кај серија ${p.batch_id}: вкупен Δ9-THC ${p.total_d9_thc} % е надвор од ${p.product_code}${w}${fall}; потребен е формален OOS за диспозицијата на серијата (${p.coq_number})`);
      }
      case 'product_created':   return AL(`${a} authored product ${p.product_code} (${p.cultivar})`,
                                          `${a} состави производ ${p.product_code} (${p.cultivar})`);
      case 'product_approved':  return AL(`${a} approved product ${p.product_code} (${p.cultivar}${p.doc_version ? ', ' + p.doc_version : ''})`,
                                          `${a} одобри производ ${p.product_code} (${p.cultivar}${p.doc_version ? ', ' + p.doc_version : ''})`);
      case 'product_ladder_created': return AL(`${a} authored the ${p.cultivar} ladder ${p.doc_version}: grades ${(p.grades || []).join(', ')}`,
                                               `${a} ја состави скалата ${p.cultivar} ${p.doc_version}: класи ${(p.grades || []).join(', ')}`);
      case 'product_catalogue_imported': return AL(`${a} imported the ImB pages ${p.doc_code} ${p.doc_version}: ${p.created} created, ${p.skipped} skipped, ${p.conflicts} conflicts`,
                                                   `${a} ги внесе ImB страниците ${p.doc_code} ${p.doc_version}: ${p.created} внесени, ${p.skipped} прескокнати, ${p.conflicts} конфликти`);
      case 'fitted_catalogue_imported':  return AL(`${a} imported the fitted specifications ${p.doc_code} ${p.doc_version}: ${p.created} created, ${p.skipped} skipped, ${p.conflicts} conflicts`,
                                                   `${a} ги внесе фитуваните спецификации ${p.doc_code} ${p.doc_version}: ${p.created} внесени, ${p.skipped} прескокнати, ${p.conflicts} конфликти`);
      // The five emitters that still fell to the generic line (review
      // 2026-09-27, INV-03): the CoQ e-signature (signatures.py), the
      // commercial identities (commercial.py), the ladder import
      // (potency_import.py) and the facility layout import (facility_layout.py).
      case 'coq_signed':         return AL(`${a} signed a certificate of quality (${p.meaning})`, `${a} потпиша сертификат за квалитет (${p.meaning})`);
      case 'commercial_identity_upserted': return AL(`${a} set the commercial identity of ${p.batch_code}${p.neu_name ? ': ' + p.neu_name : ''}`,
                                                     `${a} го постави комерцијалниот идентитет на ${p.batch_code}${p.neu_name ? ': ' + p.neu_name : ''}`);
      case 'portfolio_master_imported': return AL(`${a} imported the portfolio master: ${p.imported} commercial identities`,
                                                  `${a} го внесе портфолио регистарот: ${p.imported} комерцијални идентитети`);
      case 'potency_catalogue_imported': return AL(`${a} imported the ${p.family} potency ladders v${p.version}: ${p.created} created, ${p.skipped} skipped, ${p.conflicts} conflicts`,
                                                   `${a} ги внесе скалите на потентност ${p.family} v${p.version}: ${p.created} внесени, ${p.skipped} прескокнати, ${p.conflicts} конфликти`);
      case 'facility_layout_imported': return AL(`${a} imported the facility layout${p.source ? ' from ' + p.source : ''}: ${p.created} rooms created, ${p.updated} updated`,
                                                 `${a} го внесе распоредот на објектот${p.source ? ' од ' + p.source : ''}: ${p.created} соби креирани, ${p.updated} ажурирани`);
      default: {
        // Generic, still bilingual by structure: actor · object · action.
        // The verb is a machine word; it is printed as words, never invented.
        const verb = String(n.verb || '').replace(/_/g, ' ');
        const obj = t || objNoun(n) || '';
        return AL(`${a} · ${verb}${obj ? ': ' + obj : ''}`, `${a} · ${verb}${obj ? ': ' + obj : ''}`);
      }
    }
  };

  const REASONS = {
    assigned: { en: 'Assigned', mk: 'Доделено' }, comment: { en: 'Comment', mk: 'Коментар' },
    status: { en: 'Status', mk: 'Статус' }, report: { en: 'Report', mk: 'Извештај' },
    due: { en: 'Due', mk: 'Рок' }, mentioned: { en: '@', mk: '@' },
    // Canned automation rules (app/automation.py) — a quality role reached
    // this row without necessarily being a task participant, so the reason
    // chip carries the WHY: CAPA/validation work went stuck.
    capa_stuck: { en: 'CAPA stuck', mk: 'CAPA блокирана' },
    validation_stuck: { en: 'Validation stuck', mk: 'Валидација блокирана' },
  };

  // Digest "by action" labels — the events table's verb enum, pluralised as
  // count headings (the per-event sentence above stays the detailed render).
  const VERB_LBL = {
    created: { en: 'Created', mk: 'Креирани' }, assigned: { en: 'Assigned', mk: 'Доделени' },
    unassigned: { en: 'Unassigned', mk: 'Отстранети' }, commented: { en: 'Comments', mk: 'Коментари' },
    status_changed: { en: 'Status changes', mk: 'Промени на статус' },
    report_locked: { en: 'Reports locked', mk: 'Заклучени извештаи' },
    ack: { en: 'Acknowledged', mk: 'Потврдени' }, due_soon: { en: 'Due soon', mk: 'Наскоро рок' },
    overdue: { en: 'Overdue', mk: 'Задоцнети' },
    batch_added: { en: 'Batches added', mk: 'Додадени серии' },
    batch_moved: { en: 'Batches moved', mk: 'Преместени серии' },
    clone_run_started: { en: 'Clone runs started', mk: 'Започнати клонирања' },
    potency_deviation: { en: 'Potency deviations', mk: 'Отстапувања на јачина' },
    product_created: { en: 'Products authored', mk: 'Составени производи' },
    product_approved: { en: 'Products approved', mk: 'Одобрени производи' },
    product_ladder_created: { en: 'Ladders authored', mk: 'Составени скали' },
    product_catalogue_imported: { en: 'ImB pages imported', mk: 'Внесени ImB страници' },
    fitted_catalogue_imported: { en: 'Fitted specs imported', mk: 'Внесени фитувани спецификации' },
    handoff: { en: 'Handoffs proposed', mk: 'Предложени префрлања' },
    handoff_resolved: { en: 'Handoffs resolved', mk: 'Решени префрлања' },
    oos_opened: { en: 'OOS opened', mk: 'Отворени OOS' },
    decon_swab_positive: { en: 'Positive swabs', mk: 'Позитивни брисеви' },
    harvest_recorded: { en: 'Harvests', mk: 'Жетви' },
    trichome_checked: { en: 'Trichome checks', mk: 'Проверки на трихоми' },
    trichome_corrected: { en: 'Trichome checks corrected', mk: 'Поправени проверки на трихоми' },
    coq_signed: { en: 'CoQs signed', mk: 'Потпишани CoQ' },
    commercial_identity_upserted: { en: 'Commercial identities set', mk: 'Поставени комерцијални идентитети' },
    portfolio_master_imported: { en: 'Portfolio masters imported', mk: 'Внесени портфолио регистри' },
    potency_catalogue_imported: { en: 'Potency ladders imported', mk: 'Внесени скали на потентност' },
    facility_layout_imported: { en: 'Facility layouts imported', mk: 'Внесени распореди на објектот' },
  };
  // No backend code emits batch_closed (review 2026-09-27, FE-18) — the case
  // that handled it was dead and has been dropped; an unknown verb prints as
  // words rather than a machine token.
  const verbLabel = (v) => { const l = VERB_LBL[v]; return l ? AL(l.en, l.mk) : String(v || '').replace(/_/g, ' '); };

  // Grouped by the FACILITY's day of the instant, compared against the
  // facility's today — not the UTC day of the stamp against the browser's
  // day. Between facility midnight and 02:00 those disagreed, and an item
  // from 00:30 sat under "Yesterday" (review 2026-09-27, FE-05).
  const dayLabel = (iso) => {
    const d = GF.fmtDate(iso), today = GF.facilityToday();
    if (d === today) return AL('Today', 'Денес');
    const y = GF.fmtDate(new Date(new Date(today + 'T12:00:00Z').getTime() - 864e5).toISOString());
    if (d === y) return AL('Yesterday', 'Вчера');
    return d;
  };

  const itemRow = (n) => `
    <div class="ntf${n.read ? '' : ' unread'}" onclick="GF.WWF.openNotif('${GF.esc(n.id)}','${GF.esc(n.task_id || '')}')">
      <div class="ntf-b">
        <div class="ntf-tt">${GF.esc(sentence(n))}</div>
        <div class="ntf-meta"><span class="ntf-reason">${GF.esc(AL(REASONS[n.reason]?.en || n.reason, REASONS[n.reason]?.mk || n.reason))}</span>
          <span class="ntf-ts">${GF.esc(GF.fmtTime(n.created_at))}</span></div>
      </div>
      <button class="mini-btn ntf-done" title="${AL('Done', 'Завршено')}"
        onclick="event.stopPropagation();GF.WWF.notifDone('${GF.esc(n.id)}')">${GF.icon('check', 'icon')}</button>
    </div>`;

  // Timeline dot colour by verb class (mockup .mw-feed): completions and
  // locks read "ok", stuck-ish state changes "warn", everything else accent.
  // The acknowledgement verb is `ack` (collab.py), not 'acknowledged' — the
  // green dot never lit for one (review 2026-09-27, INV-04).
  const dotKind = (e) => e.verb === 'report_locked' || e.verb === 'ack' ? 'ok'
    : e.verb === 'overdue' || e.verb === 'due_soon' ? 'warn'
    : e.verb === 'status_changed' ? ((e.params || {}).new === 'completed' ? 'ok' : 'warn') : '';

  const feedRow = (e) => `
    <div class="ntf ntf-feed">
      <div class="ntf-rail"><span class="ntf-fdot ${dotKind(e)}"></span></div>
      <div class="ntf-b"><div class="ntf-tt">${GF.esc(sentence(e))}</div>
        <div class="ntf-meta"><span class="ntf-ts">${GF.esc(GF.fmtTime(e.created_at))}</span>
          ${e.department_id && GF.depName ? `<span class="ntf-reason">${GF.esc(GF.depAbbr(e.department_id) || '')}</span>` : ''}</div></div>
    </div>`;

  const grouped = (list, row) => {
    let out = '', last = '';
    list.forEach(n => {
      const d = dayLabel(n.created_at);
      if (d !== last) { out += `<div class="ntf-day">${GF.esc(d)}</div>`; last = d; }
      out += row(n);
    });
    return out || `<div class="ntf-empty">${AL('All clear — nothing here.', 'Сè е чисто — нема ништо.')}</div>`;
  };

  /* ── Team digest panel — "what did my team do", daily/weekly, over the
     same dept-scoped events feed (GET /notifications/digest). Collapsed by
     default; the digest is fetched lazily on first open, never as part of a
     plain notifications render. */
  const digestPanel = () => {
    const st = GF.WWF._notif;
    const dg = st.digest;
    const win = (id, lbl) => `<button class="btn btn-sm ntf-tab ${st.digestWindow === id ? 'btn-primary on' : ''}"
      onclick="event.stopPropagation();GF.WWF.setDigestWindow('${id}')">${lbl}</button>`;
    let body = '';
    if (st.digestOpen) {
      if (st.digestLoading || !dg) {
        body = `<div class="panel-body"><div class="mw-skel" style="height:52px"></div></div>`;
      } else {
        const verbChips = (dg.by_verb || []).map(v =>
          `<span class="chip-opt">${GF.esc(verbLabel(v.verb))} · ${Number(v.count) || 0}</span>`).join('');
        const actorChips = (dg.by_actor || []).map(a =>
          `<span class="chip-opt who">${GF.avatar ? GF.avatar(a.actor_id, 18) : ''}${GF.esc(who(a.actor_id))} · ${Number(a.count) || 0}</span>`).join('');
        const empty = `<span class="ntf-empty">${AL('No activity in this window.', 'Нема активност во овој период.')}</span>`;
        body = `<div class="panel-body">
          <div class="sec-label">${AL('By action', 'По дејство')}</div>
          <div class="chips">${verbChips || empty}</div>
          <div class="sec-label">${AL('By person', 'По лице')}</div>
          <div class="chips chips-who">${actorChips || empty}</div>
          <div class="sec-label">${AL('Recent', 'Неодамнешни')}</div>
          <div class="ntf-list">${grouped((dg.recent || []).slice(0, 12), feedRow)}</div>
        </div>`;
      }
    }
    return `<div class="panel" style="margin-bottom:12px">
      <div class="panel-head" onclick="GF.WWF.toggleDigest()" style="cursor:pointer">
        ${GF.icon('trend', 'icon')}<span class="ttl">${AL('Team digest', 'Тимски преглед')}</span>
        ${st.digestOpen && dg ? `<span class="cnt">${Number(dg.total) || 0}</span>` : ''}
        <div class="spacer"></div>
        ${st.digestOpen ? win('daily', AL('Daily', 'Дневно')) + win('weekly', AL('Weekly', 'Неделно')) : ''}
        ${GF.icon(st.digestOpen ? 'chevU' : 'chevD', 'icon')}
      </div>
      ${body}</div>`;
  };

  GF.views.inbox = () => {
    const st = GF.WWF._notif;
    if (!st.loaded || st.user !== GF.state.user) { GF.WWF.loadInbox(); }
    const tab = (id, lbl) => `<button class="btn btn-sm ntf-tab ${st.tab === id ? 'btn-primary on' : ''}"
      onclick="GF.WWF._notif.tab='${id}';GF.render.all()">${lbl}</button>`;
    // Client-side filter over the already-loaded st.items (see `items` below)
    // — toggling it must only re-render, never re-fetch all three data
    // sources from the server. Fetching stays reserved for initial load
    // (loadInbox() at the top of this view) and explicit refresh actions
    // (notifOlder, the poll tick, notifDone/notifReadAll's server round-trip).
    const flt = (id, lbl) => `<span class="chip-opt ${st.filter === id ? 'on' : ''}"
      onclick="GF.WWF._notif.filter=GF.WWF._notif.filter==='${id}'?'':'${id}';GF.render.all()">${lbl}</span>`;
    const items = st.filter ? st.items.filter(n => n.reason === st.filter) : st.items;
    return `${GF.viewHead ? GF.viewHead('inbox', 'inbox_sub') : `<h2>${AL('Inbox', 'Сандаче')}</h2>`}
      ${digestPanel()}
      <div class="ntf-bar">
        ${tab('inbox', AL('Inbox', 'Сандаче') + (st.unread ? ` (${st.unread})` : ''))}
        ${tab('feed', AL('Activity', 'Активност'))}
        <div style="flex:1"></div>
        ${st.tab === 'inbox' ? `<button class="btn btn-sm" onclick="GF.WWF.notifReadAll()">${AL('Mark all read', 'Означи сè прочитано')}</button>` : ''}
      </div>
      ${st.tab === 'inbox' ? `<div class="chips" style="margin:0 4px 10px">${
        Object.keys(REASONS).map(r => flt(r, AL(REASONS[r].en, REASONS[r].mk))).join('')}</div>` : ''}
      <div class="ntf-list ntf-list-enter">${!st.loaded
        ? `<div class="mw-skel" style="height:52px;margin-bottom:8px"></div>
           <div class="mw-skel" style="height:52px;margin-bottom:8px"></div>
           <div class="mw-skel" style="height:52px"></div>`
        : st.tab === 'inbox' ? grouped(items, itemRow) : grouped(st.feed, feedRow)}</div>
      ${(st.tab === 'inbox' ? st.moreItems : st.moreFeed)
        ? `<div class="mw-pager" style="justify-content:center;margin-top:10px">
             <button onclick="GF.WWF.notifOlder('${st.tab === 'inbox' ? 'items' : 'feed'}')">${AL('Load older', 'Вчитај постари')}</button></div>` : ''}`;
  };

  GF.WWF.loadInbox = async () => {
    const st = GF.WWF._notif;
    // Cross-login reset: a new session must never show the previous user's
    // items/feed/badge while its own fetch is in flight.
    if (st.user !== GF.state.user) {
      st.user = GF.state.user;
      st.items = []; st.feed = []; st.unread = 0; st.loaded = false;
      st.moreItems = false; st.moreFeed = false;
      st.digest = null; st.digestOpen = false; st.digestLoading = false;
      st._justDone = {}; st._justRead = {};
    }
    try {
      const [items, feed, uc] = await Promise.all([
        GF.API.notifications({}), GF.API.activity({}), GF.API.notifUnread()]);
      const now = Date.now();
      Object.keys(st._justDone).forEach(id => { if (st._justDone[id] < now) delete st._justDone[id]; });
      Object.keys(st._justRead).forEach(id => { if (st._justRead[id] < now) delete st._justRead[id]; });
      const fresh = (Array.isArray(items) ? items : []).filter(n => !st._justDone[n.id]);
      fresh.forEach(n => { if (st._justRead[n.id]) n.read = true; });
      st.items = fresh;
      st.feed = Array.isArray(feed) ? feed : [];
      st.unread = (uc && uc.unread) || 0; st.loaded = true;
      st.moreItems = st.items.length === PAGE; st.moreFeed = st.feed.length === PAGE;
      if (GF.state.view === 'inbox') GF.render.all(); else GF.render.sidebar();
    } catch (e) { /* offline / unauthenticated: badge just stays stale */ }
  };

  // Digest fetch — lazy (first open) + on window switch, never on a plain
  // notifications render. Stale-response guard mirrors openEdit's _editTask
  // check: a slow daily response must not clobber a newer weekly one.
  GF.WWF.toggleDigest = () => {
    const st = GF.WWF._notif;
    st.digestOpen = !st.digestOpen;
    if (st.digestOpen && !st.digest && !st.digestLoading) { GF.WWF.loadDigest(); return; }
    GF.render.all();
  };

  GF.WWF.setDigestWindow = (w) => {
    const st = GF.WWF._notif;
    if (st.digestWindow === w) return;
    st.digestWindow = w; st.digest = null;
    GF.WWF.loadDigest();
  };

  GF.WWF.loadDigest = async () => {
    const st = GF.WWF._notif;
    const w = st.digestWindow;
    const empty = { window: w, by_verb: [], by_actor: [], recent: [], total: 0 };
    st.digestLoading = true;
    GF.render.all();
    try {
      const d = await GF.API.notifDigest(w);
      if (GF.WWF._notif.digestWindow !== w) return;   // window switched while in flight
      st.digest = (d && typeof d === 'object' && Array.isArray(d.recent)) ? d : empty;
    } catch (e) {
      if (GF.WWF._notif.digestWindow !== w) return;
      st.digest = empty;
      GF.toast(AL('Digest failed: ', 'Прегледот не успеа: ') + e.message, 'error');
    } finally {
      if (GF.WWF._notif.digestWindow === w) {
        st.digestLoading = false;
        GF.render.all();
      }
    }
  };

  // Cursor pagination (mockup .mw-pager): append the next page of history
  // using the oldest loaded row as the `before` cursor.
  GF.WWF.notifOlder = async (kind) => {
    const st = GF.WWF._notif;
    const list = kind === 'feed' ? st.feed : st.items;
    if (!list.length) return;
    const before = list[list.length - 1].created_at;
    try {
      const page = kind === 'feed'
        ? await GF.API.activity({ before })
        : await GF.API.notifications({ before });
      const seen = new Set(list.map(x => x.id));
      (page || []).forEach(x => { if (!seen.has(x.id)) list.push(x); });
      if (kind === 'feed') st.moreFeed = (page || []).length === PAGE;
      else st.moreItems = (page || []).length === PAGE;
      GF.render.all();
    } catch (e) { GF.toast(AL('Load failed: ', 'Неуспешно вчитување: ') + e.message, 'error'); }
  };

  // Can the signed-in user land on the Approvals view? Mirrors the two gates
  // _registerFullPageView ANDs together for it: its module must be accessible
  // for the role (modules.js — `approvals` is a task-module key, so every
  // signed-in role passes) and the view's own guard (role !== 'USER').
  GF.WWF.canOpenApprovals = () => {
    const role = (GF.API && GF.API.user && GF.API.user.role) || '';
    if (!role || role === 'USER') return false;
    // Without the module registry (modules.js) there is no module gate to
    // fail — the same optional-chaining _registerFullPageView uses.
    if (!GF.moduleForKey || !GF.moduleAccessibleFor) return true;
    const mod = GF.moduleForKey('approvals');
    return !!mod && GF.moduleAccessibleFor(mod, role);
  };

  GF.WWF.openNotif = async (id, taskId) => {
    // Mirror notifDone/notifReadAll: a failed write must abort BEFORE the
    // optimistic local mutation below, not after — otherwise a network blip
    // or expired session silently marks the notification read / decrements
    // the badge client-side even though the server never recorded it.
    try { await GF.API.notifRead(id); } catch (e) { return; }
    const st = GF.WWF._notif;
    const n = st.items.find(x => x.id === id);
    if (n && !n.read) { n.read = true; st.unread = Math.max(0, st.unread - 1); }
    st._justRead[id] = Date.now() + 10000;
    // A handoff proposal is addressed to the receiving department, whose
    // manager cannot see the task on their own board (it still sits in the
    // source department). The place to act on it is the Approvals list of
    // handoffs to their department, not a board jump that lands nowhere
    // (review 2026-09-27, FE-06). Only when that view is OPENABLE for this
    // user, though: every task participant gets the same ping, and a USER
    // assignee (the Approvals guard is role !== 'USER') used to be sent to a
    // view render.all() bounces straight back to My Week — with no message.
    // They keep the task jump they had before (R2-FE-01).
    if (n && n.verb === 'handoff' && GF.setView && GF.WWF.canOpenApprovals()) { GF.setView('approvals'); return; }
    if (taskId && GF.WWF.xrJump) {
      const t = GF.task && GF.task(taskId);
      GF.WWF.xrJump(taskId, (t && t.week_start) || '');
    } else GF.render.all();
  };

  GF.WWF.notifDone = async (id) => {
    try { await GF.API.notifDone(id); } catch (e) { return; }
    const st = GF.WWF._notif;
    const n = st.items.find(x => x.id === id);
    if (n && !n.read) st.unread = Math.max(0, st.unread - 1);
    st.items = st.items.filter(x => x.id !== id);
    st._justDone[id] = Date.now() + 10000;
    GF.render.all();
  };

  GF.WWF.notifReadAll = async () => {
    try { await GF.API.notifReadAll(); } catch (e) { return; }
    const st = GF.WWF._notif;
    const until = Date.now() + 10000;
    st.items.forEach(n => { n.read = true; st._justRead[n.id] = until; });
    st.unread = 0;
    GF.render.all();
  };

  // 75s poll + on-focus refresh (research: polling is correct at this scale;
  // server-side unread count is the single source of truth for the badge).
  // Self-guarded: does nothing until a real session exists.
  const tick = () => {
    if (GF.API && GF.API.token) GF.WWF.loadInbox();
  };
  setInterval(tick, 75000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
  window.addEventListener('load', () => setTimeout(tick, 4000));
})();

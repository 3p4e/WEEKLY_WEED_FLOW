# QASOP_TRIAL_AD01 — §6A audit verdict and regulatory findings

Job `2f4297b9-7ceb-4f0b-8a7f-261890617c0e` · status **failed** · 2026-09-02T13:14:57 → 2026-09-02T14:55:38 UTC · error: §6A audit did not pass

## §6A audit (gf_qa_auditor)

1. **Sections 1.0, 2.0, 3.0, 6.10 and 7.0 — Invented retention citation and wrong rule for an IMP SOP.** The document repeatedly cites “EU GMP 4.11” for the retention formula “at least 1 year after expiry, minimum 5 years.” Retrieved clause 4.11 (Macedonian GMP) addresses specifications for starting materials and packaging materials, not record retention. QC documentation retention is found in Chapter 6.8. More importantly, because the document code is **QASOP_TRIAL_AD01** (investigational medicinal product), Annex 13 clause 5.5 / Delegated Regulation (EU) 2017/1569 Art 8(3) applies: batch records must be retained for **at least 5 years after completion or formal discontinuation of the last clinical trial** in which the batch was used—not from the expiry date.  
   *Action:* Remove every citation to “EU GMP 4.11” for retention. Replace the rule with the IMP-specific Annex 13 clause 5.5 retention period. If commercial product retention is also in scope, state it as a separate, explicitly scoped rule with a verifiable citation; do not blend the two.

2. **Sections 1.0, 2.0 and 3.0 (QP row) — False statement on statutory batch release authority.** The document states that “official batch release for sale / regulatory purposes remains the exclusive responsibility of an accredited laboratory.” This directly contradicts EU GMP Chapter 2.6 and Annex 16 / IMP guideline Section 8, which assign statutory batch certification and release to the **Qualified Person (QP)**. An external accredited laboratory may perform testing, but it cannot assume the QP certification duty.  
   *Action:* Rewrite to state that the QP is legally responsible for batch certification and release per EU GMP. State that the external accredited laboratory performs official release testing and issues the official CoA, which the QP uses as part of the certification decision. Align the QP responsibility text in 3.0 with this corrected role.

3. **Sections 4.0, 6.4.1, 6.6 and 8.0 — Unverifiable Ph. Eur. monograph number presented as fact.** The document cites “Ph. Eur. monograph 3028 — Cannabis flower” and attributes the acceptance criterion “±10 % Δ⁹-THC” to it. The monograph number 3028 is **not retrievable** from the available corpus. House rules require that an unknown value stay blank; never invent a document code or present an unverified number as fact.  
   *Action:* Remove “3028.” Replace with a blank field (e.g., “Ph. Eur. monograph [_____] — Cannabis flower”). In 6.6, delete the parenthetical attribution “(Ph. Eur. 3028)” from the ±10 % criterion; instead, reference the internal specification `[_____]` or a validated in-house method.

4. **Sections 1.0 and 3.0 (QA Manager) — EU GMP 6.17 misattributed to archiving/retention.** The text states that worksheets, instrument printouts, SST records, CoA and OOS records are “maintained and archived in accordance with EU GMP 6.17.” Clause 6.17 lists the **minimum data elements** to be recorded for each test (batch number, results, dates, initials, equipment reference, approval statement); it does **not** address archiving or retention of records. Archiving is addressed in clause 6.8 (and raw data in 6.10).  
   *Action:* Split the claim. State that the **content** of the records (data elements, signatures, dates, approval) is maintained per EU GMP 6.17, and that archiving/retention is performed per the applicable retention rule (Chapter 6.8 / Annex 13 5.5, as corrected in Issue 1). Do not cite 6.17 for retention or archiving.

Verdict: FIX

## Regulatory findings (gf_reg_checker, per section)

[1.0] **Findings for QASOP_TRIAL_AD01, section 1.0**

*Note: DB3_PP_CURRENT_unified reported `unknown_datasets` and is not ingested; only DB01_REG could be searched.*

{1.0, CONFLICT, DB1_REGULATORY/EudraLex/2014-11_vol4_chapter_6 - Quality Control.pdf, clauses 6.17 / 6.8 / 6.10}
The section states that worksheets, instrument printouts, sample-preparation records, SST records, CoA and OOS records are “maintained and archived in accordance with EU GMP 6.17”. Retrieved clause 6.17 lists only the minimum data elements to be recorded for each test performed (name of material, batch number, specifications, test results, dates, initials, equipment reference, and approval/rejection statement); it does not address archiving or retention of records. Retention of QC batch documentation is addressed in clause 6.8 (“retained following the principles given in chapter 4”), and raw data retention in clause 6.10.

{1.0, CONFLICT, DB1_REGULATORY/EudraLex/Part I/2014-03_chapter_2.pdf, clause 2.6; and DB1_REGULATORY/EudraLex/2014-11_vol4_chapter_6 - Quality Control.pdf, clause 6.6}
The section states that “official batch release for sale remains the exclusive responsibility of an accredited laboratory”. Retrieved Chapter 2 clause 2.6 places the statutory duty of batch release certification on the Qualified Person (QP), who must ensure each batch has been manufactured and checked in compliance with the laws in force and the marketing authorisation before certifying release. Retrieved Chapter 6 clause 6.6 permits the use of outside laboratories but requires this to be stated in QC records; it does not transfer release authority to the contract laboratory. The investigational products guidance also confirms QP certification prior to release per Annex 16 principles.

{1.0, NO-FINDING, DB3_PP_CURRENT_unified, Dataset not ingested; no Purely Plant current unified documents were available for comparison.}

---

[2.0] **Findings on section 2.0 of QASOP_TRIAL_AD01**

Dataset **DB3_PP_CURRENT_unified** was reported as `unknown_dataset` in every search; only **DB01_REG** was available. Findings below are drawn solely from the regulatory corpus that answered.

---

{2.0, **OK**, EudraLex Volume 4 Part I Chapter 6 (`2014-11_vol4_chapter_6`) clause 6.17; ДПП – Добра Производна пракса Правилник clause 6.17, The reference to worksheets and the listed dossier contents (instrument printouts, sample-preparation records, SST, CoA, OOS records) are consistent with the GMP requirement that test records include name/batch number, test results, calculations, dates, initials of tester and verifier, equipment reference, and a clear approval statement.}

{2.0, **GAP**, ДПП – Добра Производна пракса Правилник clause 6.8, The section cites “EU GMP 4.11” for the retention rule; this clause is **not verifiable** against the available corpus. The retrieved Macedonian GMP (clause 6.8) requires QC documentation to be retained “една година по истекот на рокот на употреба на серија на лекот, а најмалку 5 години од издавањето на сертификат за анализа” — i.e., one year after expiry, but at least 5 years **from the date of issue of the certificate of analysis**. The section omits that reference point for the 5-year minimum.}

{2.0, **CONFLICT**, EudraLex Volume 4 Part I Chapter 2 (`2014-03_chapter_2`) clause 2.6; EudraLex Volume 4 Annexes (`guideline_adopted_1_en_act_part1_v3`) section 8 (Release of batches), The section states that “Official batch release for regulatory purposes … remains the responsibility of the accredited external contract laboratory.” The corpus requires that a **Qualified Person (QP)** certify each batch before release (EudraLex Part I 2.6; Annex 16 IMP guideline section 8). A contract laboratory may perform testing, but it cannot assume the QP certification duty.}

{2.0, **NO-FINDING**, N/A, The “three-tier internal review,” the specific analytical techniques listed (HPLC-DAD, GC-MS, ICP-MS, gravimetric LOD, microbiological methods), and the scope covering “IPQC and trending” are internal procedural design choices not contradicted by the retrieved corpus.}

---

**Corpus availability note:** `DB3_PP_CURRENT_unified` was unavailable (`unknown_datasets`) on every query. Any facility-specific standards or cross-references held in that dataset could not be verified.

---

[3.0] {QA Manager — archiving/retention, CONFLICT, EudraLex IMP guideline (guideline_adopted_1_en_act_part1_v3.pdf) clause 5.5 / Delegated Regulation (EU) 2017/1569 Art 8(3), The SOP cites “EU GMP 4.11” for batch-documentation retention as “1 year after expiry, minimum 5 years”. The available corpus does not contain the text of EU GMP 4.11 to verify this formula. Because the document code is QASOP_TRIAL_AD01 (trial product), the retrieved IMP-specific rule in clause 5.5 applies instead: batch manufacturing records must be retained “for at least 5 years after the completion or formal discontinuation of the last clinical trial in which the batch was used”. The cited rule and formula are therefore either unverified or, if this SOP covers an investigational medicinal product, materially inconsistent with the applicable IMP retention requirement.}

{Qualified Person (QP), CONFLICT, EudraLex Part I Chapter 2.6 (2014-03_chapter_2.pdf) and IMP guideline Section 8 (guideline_adopted_1_en_act_part1_v3.pdf), The SOP states that “official release remains the responsibility of an accredited laboratory”. The retrieved EU GMP corpus assigns statutory batch certification and release to the Qualified Person (Article 62 of Regulation (EU) No 536/2014, EudraLex Chapter 2.6 and IMP guideline Section 8), not to an external accredited laboratory. This statement contradicts the QP’s legal duty and is unsupported by any retrieved passage. If a national requirement mandates release testing by an accredited external laboratory, it should be cited as national law and distinguished from the QP’s EU GMP responsibilities.}

{QA Manager — dossier content per EU GMP 6.17, OK, EudraLex Chapter 6.17 (2014-11_vol4_chapter_6 - Quality Control.pdf) and Macedonian GMP 6.17 (ДПП - Добра Производна пракса Правилник.pdf), The listed dossier contents (worksheets, instrument printouts, sample-prep records, SST records, CoA and OOS records) align with the minimum data required under 6.17: test results including observations and calculations, reference to certificates of analysis, equipment reference, and initials of the persons who performed and verified the testing.}

{Overall availability, GAP, N/A, Dataset DB3_PP_CURRENT_unified was reported as unknown_datasets in every search and was not available for retrieval. This assessment is therefore limited to DB01_REG only.}

---

[4.0] {section: 4.0, verdict: OK, citation: EMA/CTD Guide herbal drugs, section 3.2.S.4.3, note: Ph. Eur. method 2.8.13 for pesticide residues is explicitly supported in the corpus as the applicable European Pharmacopoeia method for quantitative analysis of pesticide residues on a herbal matrix.}

{section: 4.0, verdict: OK, citation: EudraLex Annex 7 (vol4_an7_2008_09_en.pdf, clauses 8 and 16) and EMA/CTD Guide herbal drugs (3.2.S.4.1 / 3.2.S.3.2), note: The corpus confirms that herbal substances require testing for water content, pesticide residues, microbial contamination / mycotoxins, toxic metals, and foreign matter per European Pharmacopoeia methods, and that identity and quality should be determined in accordance with specific Ph. Eur. monographs. The blank method numbers and internal document codes in the table are the correct treatment because the corpus does not provide specific Ph. Eur. method numbers for loss on drying, heavy metals, mycotoxins, microbial limits, or foreign matter, nor internal document codes.}

{section: 4.0, verdict: NOT-VERIFIABLE, citation: —, note: Ph. Eur. monograph number 3028 for Cannabis flower is not retrievable from the available corpus. The corpus supports the general principle that herbal substances should comply with specific Ph. Eur. monographs (EudraLex Annex 7, clause 16), but does not name this monograph number.}

{section: 4.0, verdict: GAP, citation: ragflow_scope, note: DB3_PP_CURRENT_unified is reported as unknown_dataset. The facility's internal unified document corpus is unavailable, so current internal document codes and versions listed in the table cannot be verified.}

---

[5.0] **Findings for section 5.0 of QASOP_TRIAL_AD01**

{5.0, GAP, ragflow_search response, Dataset DB3_PP_CURRENT_unified reported as unknown_datasets and is not ingested. Only DB01_REG was searchable; findings are limited to that regulatory corpus.}

{5.0, OK, EudraLex/Part I/2014-03_chapter_2.pdf §2.6 + EudraLex/Annexes/vol4_annex21_en.pdf §2.4, QP definition aligns with EU GMP: the QP certifies batch release and must ensure each batch has been manufactured and checked in compliance with the laws in force and the marketing authorisation requirements.}

{5.0, OK, EudraLex/2014-11_vol4_chapter_6.pdf §6.17 + Macedonian GMP/ДПП §6.17, Worksheets citation of EU GMP 6.17 is accurate; the clause requires test records to include name/batch, specifications, results, dates, initials, and a clear approval/rejection statement.}

{5.0, OK, EMA/CTD Guide herbal drugs.pdf §3.2.S.4.3, Pesticides reference to Ph. Eur. 2.8.13 is supported: "quantitative analysis of pesticides residues must be validated on a suitable herbal matrix (according to the indication given in European Pharmacopoeia in 2.8.13)".}

{5.0, OK, EudraLex/2014-11_vol4_chapter_6.pdf §6.7 + §6.35 + §6.9, OOS definition is consistent with EU GMP: laboratory documentation must include a procedure for the investigation of Out of Specification results, and any confirmed OOS result should be investigated and reported to the relevant competent authorities.}

{5.0, OK, EudraLex/Annexes/vol4_an7_2008_09_en.pdf §8 + §10 + EMA/CTD Guide herbal drugs.pdf §3.2.S.3.2, Definitions for foreign matter and mycotoxins align with herbal-substances guidance: tests for foreign materials and toxic metals are required; containers must be examined for adulteration/substitution and foreign matter; aflatoxins and other mycotoxins are specified contaminants.}

{5.0, GAP, EudraLex/Annexes/vol4_an7_2008_09_en.pdf §8 + EMA/CTD Guide herbal drugs.pdf §3.2.S.3.2, The retrieved corpus consistently uses "toxic metals" (токсични метали) for elemental contaminants in herbal substances. The section uses "Тешки метали~~Heavy metals". Consider aligning terminology with Ph. Eur./EU GMP usage ("toxic metals").}

{5.0, NO-FINDING, —, The remaining definitions (SST, three-tier review, trending, IPQC, potency, GC-MS, ICP-MS, HPLC-DAD, sample-prep record, instrument printout, reference standard, CRS, LOD, finished product, bulk, QC Analyst, batch analytical dossier, CoA, microbiological analysis) are either standard terms not contradicted by the corpus or not addressed by the retrieved passages.}

---

[6.0] **Findings on QASOP_TRIAL_AD01 §6.0 against DB01_REG**  
*Note: DB3_PP_CURRENT_unified is not yet ingested; only DB01_REG returned results.*

- **{6.5, OK, DB1_REGULATORY/Macedonian GMP/ДПП - Добра Производна пракса Правилник.pdf §6.17}**  
  The record-keeping requirements (contemporaneous recording, legibility, signature/date, batch number, and single-line corrections with justification) align with §6.17, which mandates that testing records include the date, initials of the tester and verifier, results, and a clear quality decision.

- **{6.10, CONFLICT, DB1_REGULATORY/Macedonian GMP/ДПП - Добра Производна пракса Правилник.pdf §6.8}**  
  The section cites “EU GMP 4.11” for retention, but the corpus places the retention rule in Chapter 6, clause 6.8: *“Целокупната документација на контролата на квалитетот … треба да се чува една година по истекот на рокот на употреба … а најмалку 5 години од издавањето на сертификат за анализа.”* EU GMP 4.11 concerns starting-material specifications, not record retention.

- **{6.4.1, NOT VERIFIABLE, no relevant passage retrieved}**  
  “Ph. Eur. 3028” and the HPLC-DAD cannabinoid potency acceptance criterion “±10 %” could not be verified against the available corpus.

- **{6.4.2, NOT VERIFIABLE, no relevant passage retrieved}**  
  “Ph. Eur. 2.8.13” as the GC-MS pesticide method could not be verified against the available corpus.

- **{6.4.4, NOT VERIFIABLE, no relevant passage retrieved}**  
  The LOD acceptance criterion “NMT 12 %” could not be verified against the available corpus.

- **{6.4.6, NOT VERIFIABLE, no relevant passage retrieved}**  
  The foreign-matter criterion “NMT 2 %” could not be verified against the available corpus.

- **{6.6, NOT VERIFIABLE, no relevant passage retrieved}**  
  The consolidated acceptance-criteria table repeats the above numeric limits (±10 % Δ⁹-THC, NMT 12 % LOD, NMT 2 % foreign matter) that could not be verified. They must be traceable to an approved internal specification; they should not be presented as corpus-confirmed facts.

**NO-FINDING** for subsections 6.1, 6.2, 6.3, 6.4.3, 6.4.5, 6.7, 6.8, 6.9, 6.11, and 6.12 — nothing in the retrieved corpus either supports or contradicts these provisions.

---

[7.0] ## Findings for section 7.0, QASOP_TRIAL_AD01

{7.0, CONFLICT, DB1_REGULATORY/Macedonian GMP/ДПП - Добра Производна пракса  Правилник.pdf clause 4.11, The section cites "EU GMP 4.11" for the retention rule "at least 1 year after the product expiry date, but not less than 5 years." The retrieved clause 4.11 from the Macedonian GMP document addresses specifications for starting materials and packaging materials (description, pharmacopoeia reference, suppliers, sampling instructions, qualitative/quantitative requirements, storage conditions, retest period). It contains no retention period requirement. The specific EU GMP Chapter 4 clause establishing the "one year after expiry / not less than five years" rule for batch documentation was not retrieved in the available corpus, so the attribution to clause 4.11 is unsupported.}

{7.0, CONFLICT, DB1_REGULATORY/EudraLex/Annexes/guideline_adopted_1_en_act_part1_v3.pdf clause 5.5, The document code "QASOP_TRIAL_AD01" indicates this SOP applies to trial (investigational medicinal) product. The retrieved Annex 13 (EudraLex Vol. 4, Annex 13) clause 5.5 states: "Batch manufacturing records should be retained by the manufacturer for at least 5 years after the completion or formal discontinuation of the last clinical trial in which the batch was used as set out in Article 8(3) of Commission Delegated Regulation (EU) No 2017/1569." The section's rule "1 year after the product expiry date, but not less than 5 years" is the commercial product rule; for IMPs the retention clock is tied to trial completion/discontinuation, not to expiry date. This is a material conflict if the SOP scope is investigational product.}

{7.0, OK, DB1_REGULATORY/EudraLex/2014-11_vol4_chapter_6 - Quality Control.pdf clause 6.8 + 6.17, EU GMP 6.17 is correctly cited. The retrieved clause 6.17 lists the required data for test records: name of material/product, batch number, references to specifications and procedures, test results including observations and calculations, dates, initials of tester and verifier, approval/rejection statement with dated signature, and equipment reference. The Macedonian version of 6.17 was also retrieved and matches. Chapter 6.8 additionally confirms that QC documentation relating to a batch record should be retained following Chapter 4 principles.}

{7.0, NO-FINDING, N/A, The corpus contains no specific requirements for the individual record types listed in the table (analytical dossier, instrument printouts, sample preparation record, SST record, CoA, OOS record) that would either support or contradict their inclusion. The table contents are not verifiable against the available corpus.}

**Note:** Dataset DB3_PP_CURRENT_unified was reported as `unknown_datasets` in every search; only DB01_REG was searched.

---

[8.0] {section: 8.0, verdict: GAP, citation: DB1_REGULATORY corpus (multiple documents), note: "Ph. Eur. 3028 'Cannabis Monograph' is not verifiable in the available corpus. The corpus contains general references to Ph. Eur. monographs for herbal substances (e.g., EudraLex Annex 7, CTD Guide) but no passage confirming monograph number 3028 specifically for cannabis. If this number is correct it should be verifiable; if not, it should be corrected or left blank."}

{section: 8.0, verdict: OK, citation: DB1_REGULATORY/EudraLex/chapter4_01-2011_en - Documentation.pdf, note: "EU GMP Guide Part I Chapter 4 'Documentation' is confirmed in corpus. The listed descriptive title 'Basic Requirements for Documentation' is a reasonable paraphrase; the actual document title is 'Documentation'."}

{section: 8.0, verdict: OK, citation: DB1_REGULATORY/EudraLex/2014-11_vol4_chapter_6 - Quality Control.pdf, note: "EU GMP Guide Part I Chapter 6 'Quality Control' is confirmed in corpus."}

{section: 8.0, verdict: OK, citation: DB1_REGULATORY/EMA/CTD Guide herbal drugs.pdf (3.2.S.4.3), note: "Ph. Eur. 2.8.13 is confirmed as the general method for pesticide residues validation."}

{section: 8.0, verdict: OK, citation: DB1_REGULATORY/EudraLex/2014-11_vol4_chapter_6 - Quality Control.pdf §6.35 / §6.7, note: "Requirement for an OOS investigation procedure is supported by EU GMP Chapter 6."}

{section: 8.0, verdict: OK, citation: DB1_REGULATORY/EudraLex/Part II/2014-08_gmp_part1.pdf §11.19 / ICH/ich-q2r2-guideline §2, note: "Reference standards and SST (System Suitability Test) requirements are supported by Part II and ICH Q2(R2)."}

{section: 8.0, verdict: OK, citation: DB1_REGULATORY/EudraLex/Part II/2014-08_gmp_part1.pdf §12.8, §12.10, §12.80, note: "Analytical method validation requirement is explicitly supported."}

{section: 8.0, verdict: OK, citation: DB1_REGULATORY/EudraLex/2014-11_vol4_chapter_6 - Quality Control.pdf §6.7 / chapter4_01-2011_en §4.31, note: "Procedures for calibration/qualification of instruments and maintenance of equipment are required by Chapter 6 and Chapter 4. The specific instrument titles (HPLC-DAD, GC-MS, ICP-MS) are facility-specific internal documents and cannot be verified against the regulatory corpus, but the general requirement is sound."}

{section: 8.0, verdict: OK, citation: DB1_REGULATORY/EudraLex/2014-11_vol4_chapter_6 - Quality Control.pdf §6.7 / WHO_TRS_902_Annex9.pdf, note: "Sampling procedures are required by Chapter 6 and WHO GMP."}

{section: 8.0, verdict: OK, citation: DB1_REGULATORY/EudraLex/Annexes/vol4_an7_2008_09_en.pdf §8 / EMA/CTD Guide herbal drugs.pdf, note: "Microbiological testing is required for herbal substances by Annex 7 and CTD guidance."}

{section: 8.0, verdict: OK, citation: DB1_REGULATORY/EudraLex/Part II/2014-08_gmp_part1.pdf §11.3 / 2014-11_vol4_chapter_6 §6.7, note: "Certificates of Analysis are a required GMP document type per Chapter 6 and Part II."}

{section: 8.0, verdict: OK, citation: DB1_REGULATORY/EudraLex/chapter4_01-2011_en §Principle / Annexes/2015-10_annex15.pdf §1.8, note: "Data integrity requirements are supported by Chapter 4 (accuracy, integrity, availability, legibility) and Annex 15."}

{section: 8.0, verdict: NOTE, citation: ragflow_search result for DB3_PP_CURRENT_unified, note: "Dataset DB3_PP_CURRENT_unified is not yet ingested in RAGflow. The titles of internal Purely Plant procedures (OOS, Reference Standards, Method Validation, instrument calibration, Sample Management, Microbiological Testing, CoA issuance, Data Integrity) cannot be cross-checked against the facility's own document register. The blank codes (________) are appropriate for a draft pending document code assignment."}

---

[9.0] NO-FINDING

*Note:* DB01_REG was searched and contains no passage that prescribes the format, column headers, or mandatory fill requirements for a document revision table in an SOP. The drafted table (Version, Date, Description of Changes, Approved By, Effective Date) is not contradicted by any retrieved regulatory text. DB3_PP_CURRENT_unified was reported as `unknown_dataset` and was not available for search.

---


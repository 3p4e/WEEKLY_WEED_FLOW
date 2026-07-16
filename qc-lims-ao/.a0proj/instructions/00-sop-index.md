# QCSOP Document Index — Purely Plant GmbH QC Laboratory

## Overview

This index catalogs all analyzed Standard Operating Procedures (SOPs) for the QC laboratory at Purely Plant GmbH. These documents form the regulatory and procedural backbone of the LIMS application.

## Available Documents (21+ files in /a0/usr/workdir/gmp_docs/)

| # | Designation | Title (EN) | Title (MK) | Key Content | LIMS Module Impact |
|---|-------------|-----------|------------|-------------|-------------------|
| 1 | QCSOP 001 | QC Department Activities | СОП за активности во сектор Контрола на квалитет | Department structure, roles, responsibilities, general QC workflow | Core — user roles, permissions, lab workflow |
| 2 | QCSOP 004 | Waste Management | Управување со отпад од лаборатории | Chemical waste disposal, segregation, labeling | Inventory — waste tracking |
| 3 | QCSOP 005 | Workwear & PPE | Работна облека и заштитна опрема | Gowning procedures, PPE requirements for QC areas | User management — training records |
| 4 | QCSOP 005 (alt) | Analytical Documentation | Работа со аналитичка документација | Lab notebook practices, data recording, calculations | Audit trail — data entry standards |
| 5 | QCSOP 008 | Measurement Traceability | Следливост на мерења | Equipment calibration, standards traceability, measurement uncertainty | Equipment module — calibration schedules |
| 6 | QCSOP 010 | Specification Issuance | Издавање на спецификација | Spec creation for finished product and packaging materials | Specification management — version control |
| 7 | QCSOP 011 | Sampling Procedures | Узорцирање | Sampling of raw materials, packaging materials, and finished product | Sample management — sampling plans |
| 8 | QCSOP 012 | Certificate of Analysis | Издавање на сертификат од анализа v.02 | COA generation, review, approval, release | COA generation — PDF output |
| 9 | QCSOP 018 | Stability Studies | Прием, складирање и испитување на мостри за стабилност | Stability chamber management, pull schedules, testing intervals | Stability module — scheduling, alerts |
| 10 | QCSOP 019 | OOS Investigation | Investigation & Handling of Out of Specification Results | OOS detection, Phase I/II investigation, CAPA | OOS module — investigation workflow |
| 11 | QCSOP 019-A01 | Internal OOS Record | Internal OOx Investigation Record | Structured investigation form, root cause analysis | OOS — investigation forms |
| 12 | QCSOP 019-A02 | External OOS Record | External OOx Investigation Record | External factor investigation form | OOS — external investigations |
| 13 | QCSOP 019-A03 | OOS Register | OOx Register | Central log of all OOS events | OOS — register/dashboard |
| 14 | QCSOP 019-A04 | OOS Notification | OOx Notification Form | Notification template for OOS events | OOS — notifications |
| 15 | QCSOP 023 | Microbiological Monitoring | Микробиолошки мониторинг | Environmental monitoring, air sampling, surface testing | Environmental monitoring module |
| 16 | QCSOP 024 | Microbiological Analysis | Аналитички постапки за микробиолошки анализи | Microbial limits testing, pathogen testing, plate counts | Micro testing module |
| 17 | QCSOP 025 | Labeling & Segregation | Procedure for Labeling, Segregation and Inventory Control | GMP-compliant labeling, segregation of materials | Inventory management module |
| 18 | QAT038.2 | Quality Assurance Template | — | QA procedure template/checklist | QA oversight module |
| 19 | QCCoA 001 | Certificate of Analysis Template | — | Standard COA format with test parameters | COA templates |
| 20 | QA_SOP_XXX | Logbook Management | Preparation, Distribution, Usage and Handling of Logbooks | Logbook lifecycle management | Audit trail — logbook tracking |

## Documents Awaiting Upload (from G:\ Drive)

| # | Designation | Title (EN) | Title (MK) | Expected Content |
|---|-------------|-----------|------------|-----------------|
| — | **Templates and Logbooks/** | Full folder | — | All template forms, logbooks, registers used in QC |
| — | **WIs/** | Work Instructions folder | — | Detailed step-by-step work instructions for lab procedures |
| 21 | QCSOP 002 | H&S in QC | БЗР во сКК | Health and safety procedures specific to QC lab |
| 22 | QCSOP 003 | Cleaning in QC | Чистење во сКК | Cleaning procedures, validation, verification for QC areas |
| 23 | QCSOP 006 | Analytical Documentation (full) | Аналитичка документација | Complete analytical doc requirements, data recording standards |
| 24 | QCSOP 007 | Data Integrity | Интегритет на податоци | ALCOA++ principles, data governance, audit trails |
| 25 | QCSOP 014 | Water System Sampling | Water system sampling and QC | Purified water (PW) / WFI sampling, testing schedule, limits |
| 26 | QCSOP 016 | Cannabinoid Testing | Канабиоиди испитување | HPLC/GC methods for cannabinoid quantification in flower and extracts |
| 27 | QCSOP 022 | Chemicals & Standards | Хемикалии и референтни стандарди | Chemical receipt, storage, inventory of reference standards |

## SOP Structure (All QCSOP Docs Follow This Pattern)

Each QCSOP document contains:
1. **Header**: Document number, version, effective date, author, approver
2. **Purpose** (bilingual MK/EN): Objective and scope of the procedure
3. **Scope**: Applicable areas, materials, personnel
4. **Definitions**: Key terms, abbreviations, references
5. **Responsibilities**: Roles with specific duties
6. **Procedure**: Step-by-step instructions in bilingual format
7. **Records**: Associated forms, logbooks, templates (with references)
8. **References**: Related SOPs, regulatory guidelines, pharmacopoeia
9. **Appendices**: Forms, templates, flowcharts
10. **Revision History**: Change log with version tracking

> **LIMS Impact**: Every SOP module maps to specific LIMS features. When building, always reference the SOP sections above for requirements.
# Feature Specification: Instructions Page

**Feature Branch**: `009-instructions-page`

**Created**: 2026-08-28

**Status**: Draft

**Input**: User description: "docs/instructions_page_requirements.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand what to gather and what each field means (Priority: P1)

A user preparing to enter their household's financial scenario reads written guidance, before or alongside filling out the scenario entry form, that explains what financial information to gather for each party in the household and what every field on that form actually requires.

**Why this priority**: Without this, a user guesses at what each field means — whether a dollar figure is gross or net, whether an account balance is entered once per household or once per person, whether a benefit estimate must match the age they plan to claim it. These are exactly the kind of silent misunderstandings that produce bad data entry and, downstream, an unreliable plan. This single piece of guidance content is the entire value of the feature — delivering it alone is a complete, usable outcome.

**Independent Test**: Can be fully tested by opening the guidance on its own, with no scenario created and no other part of the tool exercised, and confirming it explains every input group on the scenario entry form.

**Acceptance Scenarios**:

1. **Given** a user who has never used the tool before, **When** they open the guidance, **Then** they see an explanation for every input group on the scenario entry form: household/parties, accounts, spending, state, market assumptions, simulation settings, and the optional Roth conversion.
2. **Given** a user unsure whether to enter account balances once per household or once per person, **When** they read the accounts guidance, **Then** it explicitly states balances are entered as one combined household total per account type, not per person.
3. **Given** a user about to enter a party's Social Security information, **When** they read the household guidance, **Then** they understand the benefit amount they enter must correspond to the specific claiming age they enter for that party, not automatically the full-retirement-age amount.
4. **Given** a user reading the spending guidance, **When** they enter their own figure, **Then** they understand it should be in today's dollars and before taxes.

---

### User Story 2 - Find the guidance at any time (Priority: P2)

A user can reach the guidance from anywhere in the tool, before starting a scenario, mid-way through filling one out, or after already having used the tool for a while — it is not a one-time introduction they lose access to.

**Why this priority**: The guidance is only useful if it's easy to find exactly when a question comes up, which may not be a user's very first visit. This priority layers discoverability onto User Story 1's content; the content is valuable even before this is addressed, but this is what makes it actually get used.

**Independent Test**: Can be fully tested by starting from any other part of the tool and confirming the guidance is reachable in a small, constant number of steps, and that reaching it does not require a scenario to already exist.

**Acceptance Scenarios**:

1. **Given** a user on the tool's main/landing view, **When** they look for guidance on what to prepare, **Then** they find a clearly labeled way to reach it before creating any scenario.
2. **Given** a user midway through the scenario entry form, **When** they want to double-check what a field requires, **Then** they can navigate to the guidance and back without losing their place or being blocked from continuing.

---

### Edge Cases

- What happens when the list of supported states changes? The guidance must not enumerate specific state codes as if the list were fixed — it must point the user to the scenario form's own state selector for the current list, so the guidance never falls out of date on its own.
- What happens if a user skips the guidance entirely and goes straight to entering a scenario? The scenario entry form must remain fully usable on its own — the guidance is a help resource, not a required or gating step.
- What happens if a user returns to the guidance after already having created a scenario? The guidance must still be reachable and still show the same explanatory content — it does not depend on, and is not affected by, any scenario a user has already created.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST provide guidance content explaining what financial information to gather for each party in the household before completing a scenario.
- **FR-002**: The guidance MUST cover, at minimum, every input group present on the scenario entry form: household/parties, accounts, spending, state, market assumptions, simulation settings, and the optional Roth conversion.
- **FR-003**: The guidance MUST state explicitly that account balances (traditional, Roth, and taxable) are entered as one combined household total per account type, not separately per party.
- **FR-004**: The guidance MUST explain that a party's Social Security benefit figure must correspond to the specific claiming age entered for that party, not automatically the full-retirement-age amount.
- **FR-005**: The guidance MUST state that the spending figure is entered in today's (real) dollars and before taxes.
- **FR-006**: The guidance MUST direct users to the scenario form's own state selector for the current list of supported states, rather than stating a fixed list of states within the guidance itself.
- **FR-007**: The guidance for market/return assumptions MUST be presented as an example or starting point, never as an authoritative or required value.
- **FR-008**: The guidance MUST be reachable from the tool's navigation at any time, independent of whether a scenario has already been created.
- **FR-009**: The guidance MUST remain viewable even when other parts of the tool that depend on a live connection to computed or saved data are unavailable.
- **FR-010**: Viewing or not viewing the guidance MUST NOT block or gate a user's ability to create or edit a scenario.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user can, within two minutes of reading, correctly state what the "annual spending need" figure represents and whether account balances are entered per party or per household.
- **SC-002**: All seven of the scenario entry form's input groups (household/parties, accounts, spending, state, market assumptions, simulation settings, Roth conversion) have corresponding guidance content — 7 of 7.
- **SC-003**: A user can reach the guidance from anywhere else in the tool, and return to what they were doing, in two navigation actions or fewer.
- **SC-004**: The guidance content requires no update when a new state is added to the list of supported states.

## Assumptions

- The audience is the same single household/user this tool already serves — no multi-tenant, multi-user, or per-user-customized content is in scope.
- The guidance supplements the scenario entry form; it does not change that form's fields, labels, or behavior.
- Users access this guidance through the same interface as the rest of the tool.
- Content is authored once by whoever maintains the tool and is not user-editable; no content-management capability is in scope.
- English-only; no localization/translation requirement, matching the rest of the tool.

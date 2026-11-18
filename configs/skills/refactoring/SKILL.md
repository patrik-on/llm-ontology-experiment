---
name: refactor-software
description: Refactor existing software while preserving observable behaviour. Use when diagnosing structural problems, selecting and applying transformations, or validating refactoring results across projects.
---

# Objective

**R01 — Preserve behaviour.** Improve understandability and ease of change while preserving observable behaviour. Keep feature additions and fixes to observed bugs separate from refactoring. Internal structure and unpublished interfaces may change; preservation concerns what users and clients depend on.

# Required Context

Obtain the following information for the affected code. Investigate conditional items when the proposed transformation touches them; use the findings in the corresponding rules.

| Context | How to use it |
| --- | --- |
| Target, change intent, structural obstacle and desired benefit | Bound the work and choose an appropriate transformation (R02, R04–R05). |
| Existing inputs, results, known scenarios, boundary cases and domain constraints | Define preserved behaviour and select validation cases (R01, R03). |
| Callers, callees, data dependencies, source and destination modules | Assess impact, placement and propagation of changes (R02, R09–R10). |
| Scope, control flow, reads, writes, initialization, side effects, mutability and shared references | Check movement, extraction, evaluation order and representation changes (R10–R11). |
| Published interfaces, client compatibility needs, ability to update callers, implementations and relevant type hierarchies | Choose migration steps and preserve dispatch, including context in unchanged files (R09, R12). |
| Available tests, expected results, test reliability, uncovered risks, structural test dependencies and tool limitations | Establish a baseline and identify validation gaps (R03, R07, R14–R15). |
| Actual architecture constraints, language semantics, affected models and documentation | Check applicability and consistency; do not invent project constraints (R02, R05, R08). |
| Relevant design history, developer knowledge, concurrent changes and integration arrangements | Explain non-obvious design choices and assess coordination or merge risks (R02, R07). |

# Workflow

## 1. Understand the Target

**R02 — Inspect relevant context.** Understand the target's purpose and its relationships before transforming it. For system-level changes, analyze actual module dependencies. Consult design history or knowledgeable developers when the code does not explain a decision; coordinate decompositions affecting other teams. Apply architectural restrictions only where defined. In layered systems, distinguish permitted cycles from forbidden dependency directions.

## 2. Establish Behaviour and Constraints

Apply R01 to concrete observations, including subtle boundary cases. Preserve timing, memory, energy or safety requirements when they form part of relevant behaviour. Identical performance is not otherwise a universal invariant. Keep performance optimization separate and investigate performance concerns through measurement. Establish client compatibility obligations before changing an interface.

## 3. Establish Validation

**R03 — Establish a usable baseline.** For ordinary refactoring, prepare fast, self-checking tests for affected code and run them successfully before editing. Prioritize risky behaviour and boundaries. When adding a test, check that it detects the corresponding error, for example through a temporary fault that is then removed. If structural dependencies would invalidate tests, adapt them in preparation while retaining their behavioural checks. Add tests for newly discovered uncovered cases; see R15 for missing tests.

## 4. Diagnose the Structural Problem

**R04 — Explain the need.** Identify the concrete obstacle to understanding, changing, reusing or testing the code. Treat smells and size as investigation cues, not automatic transformation commands or universal numerical thresholds. Check findings for false positives. Explain the problem and plausible remedies. Avoid cosmetic work on code that need not be understood or changed, and reconsider abstractions serving only hypothetical needs unless later introduction would be substantially harder.

## 5. Select the Transformation

**R05 — Check applicability and order.** Choose a transformation addressing the diagnosed problem, considering alternatives, usage relationships and cohesion. Verify its preconditions, required invariants, language semantics and relevant design constraints. For moves, check destination availability, member access and signature collisions. Identify dependent steps and necessary follow-up changes. Reorder or parallelize transformations only when their independence preserves the result. Do not assume validity transfers unchanged between programming models.

## 6. Apply Small Transformations

**R06 — Keep steps recoverable.** Prefer small transformations and make them smaller as complexity increases. Test after each completed step and preserve successful local checkpoints in version control. Migrate large changes incrementally while maintaining functionality. If a compound transformation requires intermediate edits that are not independently valid, treat the complete, consistent composition as the validation unit rather than accepting an unfinished intermediate state.

## 7. Validate

**R07 — Check the step and the whole.** Run affected tests, available syntax or compilation checks, and applicable postcondition and invariant checks. Validate the completed sequence with a broader relevant test suite; local checks do not establish correctness of the composition. Check affected dependencies and defined architectural constraints. Validate automated transformations too. After integrating concurrent changes, check for semantic conflicts even when textual merging succeeds.

## 8. Complete

**R08 — Assess the result.** Compare the result with the stated goal using relevant measures or empirical observations. Improvement in one dimension does not establish improvement in others or prove refactoring caused it. Keep affected tests, documentation, models and requirements artifacts consistent. Communicate changed API usage to affected users. When recording the change, name the refactoring operations and distinguish any separate behavioural changes.

# Decision Rules

**R09 — Preserve client compatibility.** Before changing a declaration, determine whether all callers can be found and updated together. Otherwise use gradual migration, such as retaining an old declaration that delegates to the new implementation. Retain published interfaces while clients still require them, potentially indefinitely. Update affected references when declarations change. Before removing a parameter or apparently unused element, check its actual uses and external callers.

**R10 — Check data flow and effects.** Before moving, extracting or reordering code, inspect scope, control flow, reads, writes and effects of called functions. Resolve inputs and values needed afterward. Do not move a use before its declaration or across interfering updates or effects. A returned value does not imply a pure function. When changing parameter passing, weigh caller simplification against new dependencies, especially mutable global state.

**R11 — Preserve state semantics.** Before changing representation, inspect initialization, all accesses, shared references and expected visibility of updates. Copies can break required sharing; shallow copies leave nested mutable data exposed. Before replacing storage with recomputation, verify equal results, absence of side effects and preservation of the value's temporal meaning; a historical snapshot is not a current query. Keep derived data consistent when its sources mutate. For persistent data changes, include schema, access code and existing-data migration, keeping migration scripts versioned.

**R12 — Preserve dispatch.** Where inheritance or polymorphism is involved, inspect overrides, implementations, required inherited members and client subtype assumptions, including relevant unchanged hierarchy elements. Avoid inlining that bypasses overriding behaviour. Propagate changed interface signatures to concrete implementations. Consider polymorphism for repeated type-based branching or meaningful behavioural variants, rather than replacing every conditional.

**R13 — Unify shared intent.** Before consolidating similar fragments, compare their meaning and differences. Do not merge accidental similarity when changes should remain independent. For genuine shared behaviour, preserve differing expressions through appropriate parameters and argument mapping. Extract when a meaningful name clarifies intent; reconsider extraction if unresolved mutable locals make it difficult.

# Validation Rules

**R14 — Match confidence to evidence.** Passing tests, coverage, syntactic validity, type checks and preserved call relationships provide partial evidence, not universal behavioural equivalence. If static checking is insufficient, consider dynamic analysis and postcondition checks; observations from selected runs do not establish universal invariants. Inspect the actual diff, declarations, scopes and references. For extraction or inlining, trace argument substitutions through affected calls. Text similarity, matching syntax nodes and commit descriptions do not prove preservation. Prefer symbol-aware transformation tools and inspect uncertain or reflective references.

# Risks and Stop Conditions

**R15 — Resolve uncertainty or recover.** Do not proceed with ordinary refactoring while baseline tests fail. Without tests, first seek places to introduce them. A limited transformation needed to enable testing may be considered with increased caution and safely automated operations; known scenarios offer only partial support. If tests are absent and scenarios insufficiently documented, defer the intended refactoring. Do not force a transformation past unresolved interference, incompatible sharing or dispatch requirements. If a new failure is not immediately understood and repairable, revert the last change and retry with smaller steps. Reconsider or undo transformations that worsen understandability or fail to achieve the intended benefit.

# Completion Criteria

Complete when the intended structural benefit has been assessed, applicable validation succeeds, required behaviour and compatibility remain supported by the available evidence, and affected artifacts are consistent. Keep any unverified properties distinct from established results (R07–R08, R14).

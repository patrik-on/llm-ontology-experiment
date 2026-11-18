---
name: test-software
description: Design, implement, execute, and assess software tests from requirements, behaviour, risks, and explicit coverage criteria. Use when creating tests, investigating failures, checking changes, or evaluating an existing test suite.
---

# Objective

Find departures from expected behaviour and provide evidence about software quality and risk. Passing tests do not prove correctness. Apply the workflow iteratively to the current testing scope. [T01, T13]

# Required Context

Obtain the following project information where relevant; use it to derive tests rather than inventing its values. [T01]

- **Test basis:** requirements, intended use, specifications, interface documentation, preconditions, postconditions, and invariants. Use these to identify behaviour and justify expectations.
- **Target and inputs:** testable units, implementation where available, input domains, boundaries, special values, operational profiles, and constraints. Include implicit inputs such as state, shared values, files, and environment.
- **State and interactions:** initial states, transitions, guards, triggering events, operation ordering, interfaces, dependencies, exchanged data, and communication assumptions. Use these to prepare sequences and expose interaction faults.
- **Observations:** outputs, data changes, messages, effects on other components, and environmental state. Establish how inputs can be controlled and effects observed.
- **History:** existing tests and their criteria, previous results, bug reports, and implementation, interface, or environment changes. Use these for reproduction and regression selection.
- **Scope and constraints:** objectives, quality characteristics, product and project risks, resources, environment and data requirements, and project-defined entry, completion, suspension, and resumption criteria. Use these to set priorities and judge readiness.

# Workflow

## 1. Understand the Test Target

**T01 — Establish the basis.** Identify the target, scope, and sources of expected behaviour. Analyse the test basis for ambiguities or inconsistencies and report discovered defects. For generated unit tests, consider the complete target implementation and relevant surrounding code and dependencies within available context.

## 2. Identify Behaviour and Risk

**T02 — Prioritise explicit objectives.** Identify behaviours and failure concerns from the test basis, known problems, and analysed risks. Prioritise by risk exposure, considering impact and likelihood; record exclusions and reasons. Define completion criteria against available resources. For fault-directed cases, distinguish reaching the faulty location, producing an incorrect state, and propagating it to an observable result. Revisit priorities when risks change.

## 3. Select Test Level and Technique

**T03 — Match the level to the question.** Use unit or module testing for behaviour within a unit or related collection; integration testing for interfaces, exchanged data, and inconsistent component assumptions; system testing for whole-system requirements; acceptance testing for user needs with user or domain-expert involvement. Choose functional or nonfunctional objectives separately from the level.

**T04 — Select techniques from available models.** Identify the supporting artifact and concrete coverage items before generating cases. Consider:

| Situation and required context | Technique and target |
| --- | --- |
| Known input characteristics and domains | Partitioning and boundary selection: representative classes and values near meaningful limits. |
| Shared state, transitions, guards, and ordering rules | State and sequence testing: states, transitions, transition combinations, and ordering violations. Map sequences to executable inputs and observations. |
| Control-flow graph or user scenarios | Graph or scenario testing: selected nodes, edges, or paths, including relevant alternatives. |
| Compound predicates, clause dependencies, and reachable decisions | Logic coverage: predicate outcomes and clause influence. Consider correlated active clause coverage, using pairs where the major clause determines the predicate and both change value. |
| Definitions, uses, and paths without intervening redefinition | Data-flow testing: definition–use relationships, including values passed between components. |
| Input grammar and semantic constraints | Grammar-based testing: productions and valid strings; input mutation for malformed cases. Check intended invalidity because mutations can remain valid. |
| Input format and an effective driver | Fuzzing: diverse unexpected, invalid, or random inputs; consider seeds from historical failures. |

These are conditional choices, not a checklist requiring every technique.

## 4. Design Test Cases

**T05 — Model the input space.** Identify all influencing parameters. Partition meaningful characteristics into nonoverlapping blocks covering the modelled domain. Include valid and invalid classes where applicable. Consider boundaries and nearby values, domain-specific special values, and normal usage; boundary cases alone do not represent the operational profile.

**T06 — Select feasible combinations.** Record required and forbidden combinations. Distinguish invalid inputs worth testing from impossible combinations. Consider base-choice testing by documenting a representative baseline and varying one characteristic, or pairwise/t-wise criteria for interactions between characteristics. Coverage of each individual block does not cover their interactions. For invalid-input rejection, consider one invalidity at a time to reduce masking.

**T07 — Construct complete cases.** Specify preconditions, state preparation, inputs and actions, expected observations, and finalisation returning to the required stable state. Order dependent cases using preconditions and postconditions. For incomplete assemblies, use substitutes for missing called or calling components where needed; substitute return values must respect relevant constraints.

## 5. Define Oracles and Expected Outcomes

**T08 — Justify the verdict.** Before evaluating a case, identify the expected result or another means of assessing correctness. Derive checks from specified output properties, contracts, invariants, and relevant side effects rather than reproducing the implementation algorithm. Accept any result the specification permits. For state transitions, check the expected resulting state, accounting for alternative transitions when a guard is false.

**T09 — Address difficult oracles.** Where documentation supports meaningful properties and input generation, consider property-based tests. If exact results are difficult to determine, consider known relations between related inputs or operations, or differential testing with comparable implementations or environments on identical inputs. Investigate differences; agreement can conceal shared faults. Metamorphic relations proposed by an LLM require human assessment before use. Crash-only checks cover only a limited class of failures.

## 6. Implement and Execute

**T10 — Verify readiness and run.** Check the required target, data, and environment state; record known differences from the operational environment. Validate generated tests syntactically, compile where applicable, and execute them. Use diagnostics and relevant context to refine invalid generated tests. Automate execution and comparison where benefits justify costs, particularly for repeated regression testing. Observe actual effects, compare them with expectations, and record execution and verdicts according to the plan, including inconclusive outcomes. Preserve traceability to the test basis and coverage items.

## 7. Evaluate and Refine

**T11 — Diagnose and reassess after change.** A failure can originate in the product, test, test basis, or environment; investigate before attributing it. Use bug reports and available traces to consider a reproducing test. Verify a repair by retesting the affected behaviour; assess regression needs in unchanged parts and run the selected regression tests. Reassess suite adequacy after changes even when existing tests pass. If completion criteria remain unmet, revisit design or execution.

# Decision Rules

**T12 — Balance generation with directed design.** If automated and manually designed tests detect similar faults, prefer automated generation for speed while accounting for execution, review, and reporting costs. Consider manual design for difficult coverage targets or hard-to-kill mutants. Judge readability and usefulness alongside efficiency; neither approach is universally superior.

# Validation Rules

**T13 — Separate coverage from effectiveness.** Measure coverage on executed tests against an explicit artifact, model, and criterion. Investigate unmet items; document infeasible requirements and consider feasible weaker counterparts. Assess test correctness, readability, coverage, and fault detection separately. More tests, higher coverage, or a stronger criterion do not guarantee more detected faults. When comparing suites, consider size and distinguish seeded from naturally occurring faults.

**T14 — Use mutation conditionally.** Consider mutation analysis to assess sensitivity to a relevant fault model. First run the suite on the original program and independently verify its results; resolve detected program errors before executing mutants. With strong mutation, a differing final output distinguishes a mutant; weak mutation checks an earlier state and does not establish propagation. Investigate survivors before targeting additional tests: survival alone establishes neither equivalence nor a missing test. Calculate mutation score over non-equivalent mutants, disclose unresolved equivalence, and interpret it only for the chosen mutants. If cost is excessive, consider sampling or selective mutation and assess the loss of effectiveness. Input mutation creates test data and does not use this mutant-killing criterion.

# Risks and Stop Conditions

**T15 — Expose blockers and limits.** When expectations or observations cannot support a verdict, report the limitation and an inconclusive result. Defective tests or environments can require suspension and later resumption of affected execution. For poor controllability or observability, consider improvements or complementary review and communicate remaining risk. Instrumentation can alter timing or side effects. If completion criteria conflict with available resources, revisit the strategy and document the resulting limits.

# Completion Criteria

Evaluate completion against the selected criteria, recording coverage gaps, outcomes, incidents, exclusions, and remaining risks. Follow applicable project requirements for completion approval. Restore the environment to its predetermined state and preserve reusable tests and results with their traceability. Passing tests alone do not establish that an implementation or repair is correct. [T10, T11, T13, T15]

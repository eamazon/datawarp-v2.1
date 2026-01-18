# DATAWARP COMPREHENSIVE AUDIT FRAMEWORK

## OBJECTIVE
Systematically test EVERY pathway in USERGUIDE.md, provide evidence, and certify with confidence scores.

## CONFIDENCE SCORE CRITERIA

**🟢 95-100% - CERTIFIED**
- All pathways tested with evidence
- All edge cases handled
- All errors have helpful messages
- Complete code trace performed
- User can execute without expert knowledge

**🟡 70-94% - FUNCTIONAL WITH ISSUES**
- Main pathway works
- Some edge cases not handled
- Some errors could be clearer
- Partial code trace
- May require some expert knowledge

**🔴 0-69% - NEEDS WORK**
- Pathway broken or unreliable
- Many edge cases fail
- Poor error messages
- Code trace incomplete
- Requires expert knowledge

## AUDIT METHODOLOGY

For each pathway:

1. **MAP** - Identify the pathway from USERGUIDE.md
2. **TRACE** - Follow code execution paths
3. **TEST** - Execute with real data
4. **EDGE** - Test failure modes
5. **EVIDENCE** - Capture output/logs
6. **FIX** - Address any issues found
7. **CERTIFY** - Assign confidence score with justification

## PATHWAYS TO AUDIT (from USERGUIDE.md)

### A. SETUP & INSTALLATION
- [ ] Virtual environment creation
- [ ] Package installation
- [ ] Database setup
- [ ] Schema creation

### B. QUICK START (5 MINUTES)
- [ ] First load workflow
- [ ] Data verification
- [ ] List sources

### C. CONFIG PATTERNS (ALL 6)
- [ ] Pattern A: Monthly Publication (NHS Digital)
- [ ] Pattern B: Quarterly Publication (Specific Months)
- [ ] Pattern C: Publication with URL Exceptions
- [ ] Pattern D: Publication with Offset (SHMI)
- [ ] Pattern E: Explicit URLs (NHS England)
- [ ] Pattern F: Fiscal Quarters

### D. RUNNING BACKFILL
- [ ] Process all publications
- [ ] Process one publication
- [ ] Dry run mode
- [ ] Status command
- [ ] Retry failed
- [ ] Force reload
- [ ] Reference manifests

### E. VERIFICATION (6-ITEM CHECKLIST)
- [ ] No failed loads
- [ ] Expected periods present
- [ ] Row counts reasonable
- [ ] No critical drift events
- [ ] Parquet exports exist
- [ ] State file updated

### F. REPORTING & MONITORING
- [ ] Daily load summary
- [ ] Publication status dashboard
- [ ] Error analysis
- [ ] Pipeline performance
- [ ] Monitoring alerts

### G. TROUBLESHOOTING
- [ ] 404 Not Found
- [ ] Column mismatch/drift
- [ ] Already processed
- [ ] LLM enrichment failed
- [ ] Database errors

### H. LOG INTERROGATION
- [ ] Find run summary
- [ ] Find all errors
- [ ] Find failed periods
- [ ] Find successful periods
- [ ] Check row counts
- [ ] Track specific period

## EXECUTION PLAN

Phase 1: Map all pathways (30 min)
Phase 2: Trace code paths (1 hour)
Phase 3: Test systematically (2-3 hours)
Phase 4: Fix issues found (varies)
Phase 5: Generate certification report (30 min)

## OUTPUT FORMAT

For each pathway:

```
PATHWAY: [Name]
CONFIDENCE: [Score]% 🟢/🟡/🔴

EVIDENCE:
  - Test command: [...]
  - Output: [...]
  - Success criteria: [...]

CODE TRACE:
  - Entry point: [file:line]
  - Key functions: [...]
  - Error handling: [...]

EDGE CASES TESTED:
  ✅ [case 1]
  ✅ [case 2]
  ❌ [case 3] - ISSUE FOUND: [description]

ISSUES FOUND: [count]
FIXES APPLIED: [count]

CERTIFICATION: [Justification for score]
```


# Inherited seed to final evaluation mapping

The original 15 cases remain byte-for-byte in `inherited/promptfooconfig.yaml`. The reconstructed baseline copies that file and uses `evals/baseline_reconstructed/provider.py` with the inherited prompt, tool definitions, and mock. The final suite uses canonical facts, actual `SophieRuntime`, and persisted-state oracles. “Corrected” below means the final test changes an unsafe or invalid expectation; it does not alter the inherited seed.

| Original seed case | Final case(s) | Disposition and reason |
|---|---|---|
| Starting price | F01, S01 | Retained the independent living starting price; final oracle checks canonical fact read and spoken monthly units. |
| Entrance fee | F02, S11 | Corrected `$2,500` to the original mock's `$3,500` canonical value. |
| Medicaid | S01 | Retained the question in a stateful flow; checks the funding answer and follow-up rather than a keyword alone. |
| Large dog | F04, S07 | Corrected the welcome guarantee: original data limits dogs to 30 pounds and the dog's weight is unknown. |
| Bot question | F10 | Corrected the `not-icontains AI` test to require honest AI identity. |
| First turn follows the intro script | F17, F23 | Retained the gym fact; removed the forced “Please hold” phrase, which is not a business fact. |
| Books a tour | F20, S01, S03 | Corrected the vague “tour” keyword assertion to check available slot, confirmation and persisted booking, including a lost-slot race. |
| Relative date | F19, S01 | Corrected stale “March 10” to a fixed fixture clock and canonical local date; Sunday is closed. |
| Kosher and low sodium | F07, S05 | Corrected the broken `question` variable to `user_input`; tests each dietary claim separately. |
| Careers | F14, S09 | Corrected the inherited unrelated event URL; current openings are unconfirmed, with no invented link. |
| Couple, one with dementia | F06, S06 | Replaced friendly-only rubric with couples-policy and memory-care facts plus explicit clinical uncertainty. |
| Air conditioning | F09, S04 | Corrected generic keyword match to unknown individual thermostat/control wording, with a canonical fact lookup. |
| Two bedroom assisted living price | F08, S08 | Retained the assisted living starting price; exact two-bedroom price remains unknown. |
| Car | F18 | Corrected unconditional “yes”: no original resident car policy exists. |
| Frustrated caller | F15, S10 | Corrected a “transfer” keyword check to a persisted simulated transfer request without claiming a live connection. |

Additional final cases F03, F05, F11–F13, F16, F21–F22, F24 and S02, S11–S18 cover prompt injection, missing facts, correction, simulated requests, invalid IDs, boundary dates, malformed success, and duplicate turns. All nine canonical tools are observed in the offline suite. The final suite's deterministic assertion is `evals/assertions.py`; any case failure is a release-blocking critical failure. It does not use an LLM grader for state truth.

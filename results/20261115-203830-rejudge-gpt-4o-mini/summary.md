# Eval results · 2026-11-15 20:38

50 tasks × 3 run(s) · model `gpt-4o-mini` (temperature 0.0) · judge `gpt-4o-mini` · tasks.jsonl sha256 `837e18df8903`

## Side by side

| Metric | baseline | react |
|---|---|---|
| Task accuracy (all runs) | 50.7% (76/150) | 66.7% (100/150) |
| Avg turns (model calls) | 1.6 | 5.0 |
| Avg tool calls | 5.7 | 4.9 |
| Avg latency (s) | 2.69 | 6.46 |
| p95 latency (s) | 5.02 | 11.00 |
| Avg tokens per task | 1,878 | 7,788 |
| pass@3 | 56.0% | 82.0% |
| pass^3 | 46.0% | 52.0% |
| Tasks that flip | 5 | 15 |
| Blocked writes | 0 | 15 |
| Unnecessary clarifications | 46 | 48 |
| Tool errors | 16 | 22 |
| Budget exhausted / crashes | 1 / 0 | 4 / 0 |

## Accuracy by category

| Split | Category | baseline | react |
|---|---|---|---|
| dev | ambiguous_batch | 2/3 | 2/3 |
| dev | delete_mistake | 0/3 | 3/3 |
| dev | split_across_days | 3/3 | 1/3 |
| dev | today_already_recorded | 3/3 | 3/3 |
| dev | wrong_batch | 3/3 | 3/3 |
| dev | wrong_day | 3/3 | 3/3 |
| heldout | already_complete | 0/9 | 3/9 |
| heldout | ambiguous_batch | 1/9 | 2/9 |
| heldout | ambiguous_event_identity | 2/9 | 4/9 |
| heldout | missing_yesterday | 3/9 | 4/9 |
| heldout | partial_same_event | 0/9 | 1/9 |
| heldout | similar_unrelated | 6/9 | 5/9 |
| heldout | today_absent | 8/9 | 6/9 |
| heldout | today_already_recorded | 9/9 | 8/9 |
| general | consume | 0/6 | 6/6 |
| general | create | 9/9 | 9/9 |
| general | edge_duplicate | 0/3 | 1/3 |
| general | edge_midnight | 0/3 | 0/3 |
| general | edge_missing_batch | 3/3 | 3/3 |
| general | edge_overconsume | 0/3 | 3/3 |
| general | medical | 3/3 | 3/3 |
| general | missing_batch | 3/3 | 3/3 |
| general | preview_only | 0/3 | 0/3 |
| general | query | 12/12 | 12/12 |
| general | query_dates | 0/6 | 6/6 |
| general | summary | 0/3 | 3/3 |
| general | untracked_nutrient | 3/3 | 3/3 |

## Tasks that flip across 3 runs

- **baseline**: d02 ✓✓✗, h01 ✓✗✓, h13 ✗✗✓, h17 ✗✓✗, h18 ✗✓✗
- **react**: d02 ✗✓✓, d06 ✗✗✓, g20 ✓✗✗, h02 ✓✗✓, h03 ✗✓✗, h06 ✓✓✗, h12 ✓✗✗, h13 ✓✗✗, h14 ✓✗✗, h17 ✓✓✗, h18 ✗✓✓, h19 ✓✗✗, h22 ✗✓✓, h23 ✓✓✗, h24 ✗✓✗

## Failed runs (124)

| Controller | Task | Run | Category | First problem | Trace |
|---|---|---|---|---|---|
| baseline | d02 | 3 | ambiguous_batch | missing event: chicken pasta box 2026-11-15 dinner 0.5 | `results/20261115-203830/traces/baseline/d02_r3.json` |
| baseline | d04 | 1 | delete_mistake | missing event: tofu curry 2026-11-14 lunch 1 | `results/20261115-203830/traces/baseline/d04_r1.json` |
| baseline | d04 | 2 | delete_mistake | missing event: tofu curry 2026-11-14 lunch 1 | `results/20261115-203830/traces/baseline/d04_r2.json` |
| baseline | d04 | 3 | delete_mistake | missing event: tofu curry 2026-11-14 lunch 1 | `results/20261115-203830/traces/baseline/d04_r3.json` |
| baseline | g04 | 1 | consume | missing event: beef broccoli box 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/g04_r1.json` |
| baseline | g04 | 2 | consume | missing event: beef broccoli box 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/g04_r2.json` |
| baseline | g04 | 3 | consume | missing event: beef broccoli box 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/g04_r3.json` |
| baseline | g05 | 1 | consume | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/g05_r1.json` |
| baseline | g05 | 2 | consume | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/g05_r2.json` |
| baseline | g05 | 3 | consume | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/g05_r3.json` |
| baseline | g10 | 1 | query_dates | first call find_batches({}), expected {'name': 'get_events', 'date_from': '2026-11-13', 'date_to': '2026-11-13'} | `results/20261115-203830/traces/baseline/g10_r1.json` |
| baseline | g10 | 2 | query_dates | first call find_batches({}), expected {'name': 'get_events', 'date_from': '2026-11-13', 'date_to': '2026-11-13'} | `results/20261115-203830/traces/baseline/g10_r2.json` |
| baseline | g10 | 3 | query_dates | first call find_batches({}), expected {'name': 'get_events', 'date_from': '2026-11-13', 'date_to': '2026-11-13'} | `results/20261115-203830/traces/baseline/g10_r3.json` |
| baseline | g11 | 1 | query_dates | first call find_batches({}), expected {'name': 'get_events', 'date_from': '2026-11-12', 'date_to': '2026-11-14'} | `results/20261115-203830/traces/baseline/g11_r1.json` |
| baseline | g11 | 2 | query_dates | first call find_batches({}), expected {'name': 'get_events', 'date_from': '2026-11-12', 'date_to': '2026-11-14'} | `results/20261115-203830/traces/baseline/g11_r2.json` |
| baseline | g11 | 3 | query_dates | first call find_batches({}), expected {'name': 'get_events', 'date_from': '2026-11-12', 'date_to': '2026-11-14'} | `results/20261115-203830/traces/baseline/g11_r3.json` |
| baseline | g12 | 1 | summary | judge: fails 'Correct: every fact in the reply matches the meal log': The assistant incorrectly stated that 3 servings of turkey chili are left, while the log indicates there are 2.5 servings left. | `results/20261115-203830/traces/baseline/g12_r1.json` |
| baseline | g12 | 2 | summary | judge: fails 'Correct: every fact in the reply matches the meal log': The assistant incorrectly states that 2 servings of Chicken Rice Box were eaten since Saturday, while only 1 serving was eaten on Saturday and none on Sunday. | `results/20261115-203830/traces/baseline/g12_r2.json` |
| baseline | g12 | 3 | summary | judge: fails 'Correct: every fact in the reply matches the meal log': The assistant incorrectly stated that 3 servings of turkey chili are left, while the log indicates there are 2.5 servings left. | `results/20261115-203830/traces/baseline/g12_r3.json` |
| baseline | g13 | 1 | preview_only | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/g13_r1.json` |
| baseline | g13 | 2 | preview_only | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/g13_r2.json` |
| baseline | g13 | 3 | preview_only | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/g13_r3.json` |
| baseline | g17 | 1 | edge_overconsume | judge: fails 'tells the user only 0.5 serving of tofu curry is left': The assistant did not inform the user that only 0.5 servings of tofu curry are left. | `results/20261115-203830/traces/baseline/g17_r1.json` |
| baseline | g17 | 2 | edge_overconsume | judge: fails 'tells the user only 0.5 serving of tofu curry is left': The assistant did not inform the user that only 0.5 servings of tofu curry are left. | `results/20261115-203830/traces/baseline/g17_r2.json` |
| baseline | g17 | 3 | edge_overconsume | judge: fails 'tells the user only 0.5 serving of tofu curry is left': The assistant did not inform the user that only 0.5 servings of tofu curry are left in the log. | `results/20261115-203830/traces/baseline/g17_r3.json` |
| baseline | g18 | 1 | edge_midnight | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/g18_r1.json` |
| baseline | g18 | 2 | edge_midnight | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/g18_r2.json` |
| baseline | g18 | 3 | edge_midnight | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/g18_r3.json` |
| baseline | g20 | 1 | edge_duplicate | unexpected event: chicken rice box 2026-11-15 lunch 1 | `results/20261115-203830/traces/baseline/g20_r1.json` |
| baseline | g20 | 2 | edge_duplicate | unexpected event: chicken rice box 2026-11-15 lunch 1 | `results/20261115-203830/traces/baseline/g20_r2.json` |
| baseline | g20 | 3 | edge_duplicate | unexpected event: chicken rice box 2026-11-15 lunch 1 | `results/20261115-203830/traces/baseline/g20_r3.json` |
| baseline | h01 | 2 | today_absent | missing event: chicken rice box 2026-11-16 any meal 0.5 | `results/20261115-203830/traces/baseline/h01_r2.json` |
| baseline | h07 | 1 | already_complete | judge: fails 'says the log already shows half yesterday and half today': The assistant did not mention that the log already shows half eaten yesterday and half today. | `results/20261115-203830/traces/baseline/h07_r1.json` |
| baseline | h07 | 2 | already_complete | judge: fails 'says no change is needed': The assistant did not explicitly state that no change is needed; it only mentioned that it did not change anything. | `results/20261115-203830/traces/baseline/h07_r2.json` |
| baseline | h07 | 3 | already_complete | judge: fails 'says no change is needed': The assistant explicitly states that it did not change anything, but it does not say that no change is needed. | `results/20261115-203830/traces/baseline/h07_r3.json` |
| baseline | h08 | 1 | already_complete | missing event: turkey chili 2026-11-16 lunch 0.75 | `results/20261115-203830/traces/baseline/h08_r1.json` |
| baseline | h08 | 2 | already_complete | missing event: turkey chili 2026-11-16 lunch 0.75 | `results/20261115-203830/traces/baseline/h08_r2.json` |
| baseline | h08 | 3 | already_complete | missing event: turkey chili 2026-11-16 lunch 0.75 | `results/20261115-203830/traces/baseline/h08_r3.json` |
| baseline | h09 | 1 | already_complete | missing event: tofu curry 2026-11-18 lunch 0.5 | `results/20261115-203830/traces/baseline/h09_r1.json` |
| baseline | h09 | 2 | already_complete | missing event: tofu curry 2026-11-18 lunch 0.5 | `results/20261115-203830/traces/baseline/h09_r2.json` |
| baseline | h09 | 3 | already_complete | missing event: tofu curry 2026-11-18 lunch 0.5 | `results/20261115-203830/traces/baseline/h09_r3.json` |
| baseline | h10 | 1 | partial_same_event | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/baseline/h10_r1.json` |
| baseline | h10 | 2 | partial_same_event | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/baseline/h10_r2.json` |
| baseline | h10 | 3 | partial_same_event | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/baseline/h10_r3.json` |
| baseline | h11 | 1 | partial_same_event | unexpected event: beef broccoli box 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/h11_r1.json` |
| baseline | h11 | 2 | partial_same_event | unexpected event: beef broccoli box 2026-11-15 dinner 1 | `results/20261115-203830/traces/baseline/h11_r2.json` |
| baseline | h11 | 3 | partial_same_event | missing event: beef broccoli box 2026-11-16 dinner 0.75 | `results/20261115-203830/traces/baseline/h11_r3.json` |
| baseline | h12 | 1 | partial_same_event | missing event: overnight oats jar 2026-11-18 breakfast 0.5 | `results/20261115-203830/traces/baseline/h12_r1.json` |
| baseline | h12 | 2 | partial_same_event | missing event: overnight oats jar 2026-11-18 breakfast 0.5 | `results/20261115-203830/traces/baseline/h12_r2.json` |
| baseline | h12 | 3 | partial_same_event | missing event: overnight oats jar 2026-11-18 breakfast 0.5 | `results/20261115-203830/traces/baseline/h12_r3.json` |
| baseline | h13 | 1 | ambiguous_batch | missing event: turkey chili 2026-11-15 dinner 0.5 | `results/20261115-203830/traces/baseline/h13_r1.json` |
| baseline | h13 | 2 | ambiguous_batch | missing event: turkey chili 2026-11-15 dinner 0.5 | `results/20261115-203830/traces/baseline/h13_r2.json` |
| baseline | h14 | 1 | ambiguous_batch | missing event: beef broccoli box 2026-11-17 lunch 1 | `results/20261115-203830/traces/baseline/h14_r1.json` |
| baseline | h14 | 2 | ambiguous_batch | missing event: beef taco bowl 2026-11-17 dinner 0.5 | `results/20261115-203830/traces/baseline/h14_r2.json` |
| baseline | h14 | 3 | ambiguous_batch | missing event: beef broccoli box 2026-11-17 lunch 1 | `results/20261115-203830/traces/baseline/h14_r3.json` |
| baseline | h15 | 1 | ambiguous_batch | missing event: chickpea curry 2026-11-15 dinner 0.25 | `results/20261115-203830/traces/baseline/h15_r1.json` |
| baseline | h15 | 2 | ambiguous_batch | missing event: chickpea curry 2026-11-15 dinner 0.25 | `results/20261115-203830/traces/baseline/h15_r2.json` |
| baseline | h15 | 3 | ambiguous_batch | missing event: chickpea curry 2026-11-15 dinner 0.25 | `results/20261115-203830/traces/baseline/h15_r3.json` |
| baseline | h16 | 1 | ambiguous_event_identity | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/baseline/h16_r1.json` |
| baseline | h16 | 2 | ambiguous_event_identity | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/baseline/h16_r2.json` |
| baseline | h16 | 3 | ambiguous_event_identity | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/baseline/h16_r3.json` |
| baseline | h17 | 1 | ambiguous_event_identity | missing event: turkey chili 2026-11-16 lunch 0.5 | `results/20261115-203830/traces/baseline/h17_r1.json` |
| baseline | h17 | 3 | ambiguous_event_identity | missing event: turkey chili 2026-11-16 dinner 0.5 | `results/20261115-203830/traces/baseline/h17_r3.json` |
| baseline | h18 | 1 | ambiguous_event_identity | missing event: beef broccoli box 2026-11-16 lunch 0.5 | `results/20261115-203830/traces/baseline/h18_r1.json` |
| baseline | h18 | 3 | ambiguous_event_identity | missing event: beef broccoli box 2026-11-16 lunch 0.5 | `results/20261115-203830/traces/baseline/h18_r3.json` |
| baseline | h19 | 1 | missing_yesterday | missing event: tofu curry 2026-11-14 lunch 1 | `results/20261115-203830/traces/baseline/h19_r1.json` |
| baseline | h19 | 2 | missing_yesterday | missing event: tofu curry 2026-11-14 lunch 1 | `results/20261115-203830/traces/baseline/h19_r2.json` |
| baseline | h19 | 3 | missing_yesterday | missing event: tofu curry 2026-11-14 lunch 1 | `results/20261115-203830/traces/baseline/h19_r3.json` |
| baseline | h20 | 1 | missing_yesterday | missing event: turkey chili 2026-11-15 dinner 0.5 | `results/20261115-203830/traces/baseline/h20_r1.json` |
| baseline | h20 | 2 | missing_yesterday | missing event: turkey chili 2026-11-15 dinner 0.5 | `results/20261115-203830/traces/baseline/h20_r2.json` |
| baseline | h20 | 3 | missing_yesterday | missing event: turkey chili 2026-11-15 dinner 0.5 | `results/20261115-203830/traces/baseline/h20_r3.json` |
| baseline | h24 | 1 | similar_unrelated | missing event: tofu curry 2026-11-18 lunch 0.5 | `results/20261115-203830/traces/baseline/h24_r1.json` |
| baseline | h24 | 2 | similar_unrelated | missing event: tofu curry 2026-11-18 lunch 0.5 | `results/20261115-203830/traces/baseline/h24_r2.json` |
| baseline | h24 | 3 | similar_unrelated | missing event: tofu curry 2026-11-18 lunch 0.5 | `results/20261115-203830/traces/baseline/h24_r3.json` |
| react | d02 | 1 | ambiguous_batch | missing event: chicken pasta box 2026-11-15 dinner 0.5 | `results/20261115-203830/traces/react/d02_r1.json` |
| react | d06 | 1 | split_across_days | blocked write: stale preview | `results/20261115-203830/traces/react/d06_r1.json` |
| react | d06 | 2 | split_across_days | blocked write: stale preview | `results/20261115-203830/traces/react/d06_r2.json` |
| react | g13 | 1 | preview_only | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/react/g13_r1.json` |
| react | g13 | 2 | preview_only | judge: fails 'Correct: every fact in the reply matches the meal log': The assistant incorrectly stated that the user logged 1.0 serving of turkey chili for dinner on November 15, 2026, when the log shows it was actually 1 serving. | `results/20261115-203830/traces/react/g13_r2.json` |
| react | g13 | 3 | preview_only | judge: fails 'Correct: every fact in the reply matches the meal log': The assistant incorrectly stated that the user logged 1.0 serving of turkey chili for dinner on November 15, 2026, when the log shows it was actually 1 serving. | `results/20261115-203830/traces/react/g13_r3.json` |
| react | g18 | 1 | edge_midnight | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/react/g18_r1.json` |
| react | g18 | 2 | edge_midnight | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/react/g18_r2.json` |
| react | g18 | 3 | edge_midnight | missing event: turkey chili 2026-11-15 dinner 1 | `results/20261115-203830/traces/react/g18_r3.json` |
| react | g20 | 2 | edge_duplicate | unexpected event: chicken rice box 2026-11-15 lunch 1 | `results/20261115-203830/traces/react/g20_r2.json` |
| react | g20 | 3 | edge_duplicate | unexpected event: chicken rice box 2026-11-15 lunch 1 | `results/20261115-203830/traces/react/g20_r3.json` |
| react | h02 | 2 | today_absent | missing event: turkey chili 2026-11-16 lunch 0.75 | `results/20261115-203830/traces/react/h02_r2.json` |
| react | h03 | 1 | today_absent | missing event: tofu curry 2026-11-17 lunch 0.5 | `results/20261115-203830/traces/react/h03_r1.json` |
| react | h03 | 3 | today_absent | missing event: tofu curry 2026-11-17 lunch 0.5 | `results/20261115-203830/traces/react/h03_r3.json` |
| react | h06 | 3 | today_already_recorded | missing event: overnight oats jar 2026-11-17 breakfast 0.5 | `results/20261115-203830/traces/react/h06_r3.json` |
| react | h07 | 1 | already_complete | missing event: chicken rice box 2026-11-16 lunch 0.5 | `results/20261115-203830/traces/react/h07_r1.json` |
| react | h07 | 2 | already_complete | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/react/h07_r2.json` |
| react | h07 | 3 | already_complete | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/react/h07_r3.json` |
| react | h09 | 1 | already_complete | missing event: tofu curry 2026-11-18 lunch 0.5 | `results/20261115-203830/traces/react/h09_r1.json` |
| react | h09 | 2 | already_complete | missing event: tofu curry 2026-11-18 lunch 0.5 | `results/20261115-203830/traces/react/h09_r2.json` |
| react | h09 | 3 | already_complete | missing event: tofu curry 2026-11-17 lunch 0.5 | `results/20261115-203830/traces/react/h09_r3.json` |
| react | h10 | 1 | partial_same_event | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/react/h10_r1.json` |
| react | h10 | 2 | partial_same_event | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/react/h10_r2.json` |
| react | h10 | 3 | partial_same_event | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/react/h10_r3.json` |
| react | h11 | 1 | partial_same_event | missing event: beef broccoli box 2026-11-16 dinner 0.75 | `results/20261115-203830/traces/react/h11_r1.json` |
| react | h11 | 2 | partial_same_event | missing event: beef broccoli box 2026-11-15 dinner 0.25 | `results/20261115-203830/traces/react/h11_r2.json` |
| react | h11 | 3 | partial_same_event | missing event: beef broccoli box 2026-11-16 dinner 0.75 | `results/20261115-203830/traces/react/h11_r3.json` |
| react | h12 | 2 | partial_same_event | missing event: overnight oats jar 2026-11-18 breakfast 0.5 | `results/20261115-203830/traces/react/h12_r2.json` |
| react | h12 | 3 | partial_same_event | missing event: overnight oats jar 2026-11-17 breakfast 0.5 | `results/20261115-203830/traces/react/h12_r3.json` |
| react | h13 | 2 | ambiguous_batch | missing event: turkey chili 2026-11-15 lunch 1 | `results/20261115-203830/traces/react/h13_r2.json` |
| react | h13 | 3 | ambiguous_batch | missing event: turkey chili 2026-11-15 dinner 0.5 | `results/20261115-203830/traces/react/h13_r3.json` |
| react | h14 | 2 | ambiguous_batch | missing event: beef taco bowl 2026-11-18 any meal 0.5 | `results/20261115-203830/traces/react/h14_r2.json` |
| react | h14 | 3 | ambiguous_batch | missing event: beef taco bowl 2026-11-17 dinner 0.5 | `results/20261115-203830/traces/react/h14_r3.json` |
| react | h15 | 1 | ambiguous_batch | missing event: tofu curry 2026-11-15 lunch 1 | `results/20261115-203830/traces/react/h15_r1.json` |
| react | h15 | 2 | ambiguous_batch | missing event: chickpea curry 2026-11-15 dinner 0.25 | `results/20261115-203830/traces/react/h15_r2.json` |
| react | h15 | 3 | ambiguous_batch | missing event: chickpea curry 2026-11-15 dinner 0.25 | `results/20261115-203830/traces/react/h15_r3.json` |
| react | h16 | 1 | ambiguous_event_identity | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/react/h16_r1.json` |
| react | h16 | 2 | ambiguous_event_identity | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/react/h16_r2.json` |
| react | h16 | 3 | ambiguous_event_identity | missing event: chicken rice box 2026-11-15 lunch 0.5 | `results/20261115-203830/traces/react/h16_r3.json` |
| react | h17 | 3 | ambiguous_event_identity | missing event: turkey chili 2026-11-15 dinner 0.5 | `results/20261115-203830/traces/react/h17_r3.json` |
| react | h18 | 1 | ambiguous_event_identity | missing event: beef broccoli box 2026-11-16 lunch 0.5 | `results/20261115-203830/traces/react/h18_r1.json` |
| react | h19 | 2 | missing_yesterday | missing event: chicken rice box 2026-11-15 lunch 1 | `results/20261115-203830/traces/react/h19_r2.json` |
| react | h19 | 3 | missing_yesterday | missing event: chicken rice box 2026-11-15 lunch 1 | `results/20261115-203830/traces/react/h19_r3.json` |
| react | h20 | 1 | missing_yesterday | missing event: turkey chili 2026-11-16 any meal 0.5 | `results/20261115-203830/traces/react/h20_r1.json` |
| react | h20 | 2 | missing_yesterday | unexpected event: turkey chili 2026-11-14 dinner 1 | `results/20261115-203830/traces/react/h20_r2.json` |
| react | h20 | 3 | missing_yesterday | missing event: turkey chili 2026-11-16 any meal 0.5 | `results/20261115-203830/traces/react/h20_r3.json` |
| react | h22 | 1 | similar_unrelated | missing event: beef broccoli box 2026-11-16 lunch 0.5 | `results/20261115-203830/traces/react/h22_r1.json` |
| react | h23 | 3 | similar_unrelated | missing event: turkey chili 2026-11-16 lunch 0.75 | `results/20261115-203830/traces/react/h23_r3.json` |
| react | h24 | 1 | similar_unrelated | missing event: tofu curry 2026-11-18 lunch 0.5 | `results/20261115-203830/traces/react/h24_r1.json` |
| react | h24 | 3 | similar_unrelated | missing event: tofu curry 2026-11-18 lunch 0.5 | `results/20261115-203830/traces/react/h24_r3.json` |

Turns = model calls per task. Latency is wall time per task and excludes the judge. Ceilings per task: {'model_calls': 12, 'tool_calls': 24, 'tokens': 16000, 'clarify_rounds': 3}. Judge tokens (not in the table): 68,825.

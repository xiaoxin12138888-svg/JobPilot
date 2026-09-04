# JD Analysis Bad Cases

## Status

No real Bad Case is recorded yet. Prompt V1 has not been run because this environment has no
configured Provider, and the candidate gold labels are still pending human review. Inventing cases
or metrics would make the evaluation misleading.

The following required categories are the review taxonomy, not observed findings:

| Category | Observed V1 cases |
| --- | --- |
| 职责识别成硬性要求 | Not run |
| 硬性要求识别成加分项 | Not run |
| 加分项识别成硬性要求 | Not run |
| 公司介绍被识别 | Not run |
| 福利被识别 | Not run |
| 缺失学历被补全 | Not run |
| 缺失经验被补全 | Not run |
| evidence 幻觉 | Not run |
| 重复项 | Not run |
| 过度总结导致语义改变 | Not run |

## Recording rule

After the first real V1 run, add only cases visible in its validated per-sample output. Each entry
must identify the sample ID, expected label, actual field, category and the smallest prompt/schema
change proposed. Prompt V2 changes must link back to one or more entries here.

# Public false-completion cases

Run `python corpus/replay.py` from the Hidden Viper directory. Each line contains a receipt, verdict and link to the observed report. The cases come from three public runs of the same workflow on November 19, 2026.

| Public run | What the final report printed | Independently observed state | Expected verifier result |
| --- | --- | --- | --- |
| [Original report](https://github.com/clarkandwebbV10/ruflo/actions/runs/44559314121/job/135684512785) | Overall success, 0 of 0 tests passed | Setup failed, all four integration jobs skipped, only the final report was uploaded | CONTRADICTED |
| [Report after fixture labeling](https://github.com/clarkandwebbV10/ruflo/actions/runs/44582410370/job/135766713543) | Overall success, 0 of 0 tests passed | Setup failed, all four integration jobs skipped, only the final report was uploaded | CONTRADICTED |
| [Corrected report](https://github.com/clarkandwebbV10/ruflo/actions/runs/44583377147/job/135771186907) | Overall failure, 0 of 0 tests passed | Setup failed, all four integration jobs skipped, only the final report was uploaded | VERIFIED |

The first two records show the same failure mechanism in different runs. The third is a control. Its verdict confirms that the report correctly described failure. It supplies no evidence of successful integration. All three cases concern the accuracy of a fixture report. They establish nothing about live agents or the cause of setup failure.

`ruflo-runs.json` contains public job IDs, job conclusions, artifact listings and two timestamped lines from each report. The replay derives the observed failure from the setup job, the four skipped producers and the artifact listing. It registers this observation with Hidden Viper's `file_contains` verifier so the provider-reported result can be checked independently. Removing a producer observation yields `UNVERIFIED`.

## Repeat from original sources

For each row, make a folder named for its run ID. Save the GitHub Actions jobs response as `jobs.json`, the artifacts response as `artifacts.json`, and the final report job log as `report.log`. The calls below show the first case. Replace both IDs for the other two cases. GitHub may require authentication for log downloads and eventually expires logs and artifacts.

```sh
gh api repos/clarkandwebbV10/ruflo/actions/runs/44559314121/jobs > 44559314121/jobs.json
gh api repos/clarkandwebbV10/ruflo/actions/runs/44559314121/artifacts > 44559314121/artifacts.json
gh api repos/clarkandwebbV10/ruflo/actions/jobs/135684512785/logs > 44559314121/report.log
python corpus/replay.py --downloads .
```


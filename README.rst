This repository contains code for a bot that monitors the fio mailing list,
pushes patch series to test branches, and reports test results back to the
mailing list. This is accomplished via a GitHub Actions workflow that:

- Runs a Python script to query the fio mailing list for new patch series.
- Then for each new patch series a new branch is created at
  https://github.com/fiotestbot/fio/branches for testing.
- The same Python script as above is also run with an option to query GitHub
  for completed tests. If found the script reports the results back to the
  mailing list.

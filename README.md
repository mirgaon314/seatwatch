# seatwatch

Checks the public UIUC Course Explorer page every 5 minutes and sends a phone push (ntfy) when a watched
section opens. It only reads the public schedule page; it never logs in or registers.

- What is watched: `WATCH` in `watch.py`
- Phone push: the `NTFY_TOPIC` repository secret (subscribe to the same topic in the ntfy app)
- Test: Actions → seatwatch → Run workflow → tick "test"
- Stop: disable the workflow in the Actions tab

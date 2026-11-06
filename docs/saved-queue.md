# Saved queue evidence

`--live-queue` collects `postqueue -j` now. `--queue-file` replays saved JSONL and does not infer when it was collected from import time, file modification time or message arrival time.

When the observation time is known:

```sh
mailforensics explain --file mail.log --queue-file queue.jsonl \
  --queue-observed-at 2026-10-04T04:00:00Z --queue ABC123
```

The timestamp must include a UTC offset. It applies to every queue file in that invocation; only combine files taken at that observation time. A saved observation can supersede an earlier delivery record, but is described as presence at the saved observation, never current presence.

Without the flag, entries have unknown age. They remain available for correlation and inspection, cannot supersede timed delivery evidence, and are excluded from elapsed-time calculations. JSON event timestamps are null for these entries; text and HTML label the observation time unknown. The existing `recipient_results.live_queue` JSON field is retained for compatibility and can contain a `queue-snapshot` event with a known historical timestamp. Inspect its kind and observation metadata before treating it as live evidence.

Raw queue files do not establish a source hostname. Their host remains `-`; narrow inputs when the same queue ID appears on multiple mail hosts. The parser API retains `live=True` for existing live-collection callers; use `live=False` for saved input and supply `captured_at` only when known.

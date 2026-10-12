-- 00_staging.sql : typed views over the raw CSV files
CREATE OR REPLACE VIEW units   AS SELECT * FROM read_csv_auto('data/units.csv');
CREATE OR REPLACE VIEW daily   AS SELECT d.*, u.site, u.model, u.unit_type
                                  FROM read_csv_auto('data/daily_operations.csv') d JOIN units u USING (unit_id);
CREATE OR REPLACE VIEW events  AS SELECT e.*, u.site, u.model,
                                         DATE_DIFF('minute', start_time, end_time) / 60.0 AS duration_h
                                  FROM read_csv_auto('data/downtime_events.csv') e JOIN units u USING (unit_id);
CREATE OR REPLACE VIEW pm      AS SELECT * FROM read_csv_auto('data/pm_services.csv');

-- Entirely synthetic. Loaded only into a disposable evaluation database.
INSERT INTO listening_events (
 event_id, event_type, event_timestamp_local, song_name, album_name, device_type,
 listening_duration_ms, media_duration_ms, duration_exceeds_media, duration_quality,
 completion_percent, is_natural_end, is_skipped, is_listening_event
) VALUES
 ('a','PLAY_END','2026-07-01','Shared','Album A','IPHONE',3600000,1800000,true,'exceeds_media',100,true,false,true),
 ('b','PLAY_END','2026-07-02','Shared','Album A','IPHONE',1800000,1800000,false,'valid',100,false,true,true),
 ('b2','PLAY_END','2026-07-03','Shared','Album A','IPHONE',1800000,1800000,false,'valid',100,true,false,true),
 ('c','PLAY_END','2026-08-01','Shared','Album B','MACINTOSH',3600000,3600000,false,'valid',100,false,true,true),
 ('d','PLAY_END',NULL,'Other','Album C','  ',3600000,3600000,false,'valid',100,true,false,true),
 ('e','PLAY_END','2026-08-31','Other','Album C','IPHONE',1800000,1800000,false,'valid',100,false,true,true),
 ('f','PLAY_END','2026-09-01','Boundary','Album D','IPHONE',3600000,3600000,false,'valid',100,true,false,true),
 ('scrub','PLAY_END','2026-07-01','Excluded','Audit','IPHONE',3600000,3600000,false,'valid',100,false,false,false);

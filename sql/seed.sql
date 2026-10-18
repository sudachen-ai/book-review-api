-- Neutral sample data for the public demo (replaces the private seed from the course version).
INSERT INTO genre (name) VALUES ('fiction'), ('non-fiction'), ('cs'), ('history');
INSERT INTO read_status (name) VALUES ('to read'), ('reading'), ('finished'), ('abandoned');
INSERT INTO author (name) VALUES ('Ursula K. Le Guin'), ('Donald Knuth'), ('Mary Beard'), ('Ted Chiang');
INSERT INTO book (title, englishtitle, genre_id, status_id) VALUES
  ('The Left Hand of Darkness', 'The Left Hand of Darkness', 1, 3),
  ('The Art of Computer Programming, Vol. 1', 'The Art of Computer Programming, Vol. 1', 3, 2),
  ('SPQR', 'SPQR: A History of Ancient Rome', 4, 1),
  ('Exhalation', 'Exhalation', 1, 3);
INSERT INTO booktoauthor (book_id, author_id) VALUES (1, 1), (2, 2), (3, 3), (4, 4);
INSERT INTO review (book_id, review_number, rating, notes) VALUES
  (1, 1, 5, 'Worldbuilding that treats politics as weather. Finished in two sittings.'),
  (4, 1, 4, 'The title story is the best; a few others feel like sketches.'),
  (4, 2, 5, 'Re-read. Anxiety Is the Dizziness of Freedom holds up.');

-- CREATE TABLES

DROP TABLE IF EXISTS review;
DROP TABLE IF EXISTS booktoauthor;
DROP TABLE IF EXISTS book;
DROP TABLE IF EXISTS author;
DROP TABLE IF EXISTS genre;
DROP TABLE IF EXISTS read_status;

CREATE TABLE author (
    author_id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(120) NOT NULL,
    PRIMARY KEY (author_id),
    UNIQUE KEY (name)
);

CREATE TABLE genre (
    genre_id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(60) NOT NULL,
    PRIMARY KEY (genre_id),
    UNIQUE KEY (name)
);

CREATE TABLE read_status (
    status_id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(40) NOT NULL,
    PRIMARY KEY (status_id),
    UNIQUE KEY (name)
);

CREATE TABLE book (
    book_id INT NOT NULL AUTO_INCREMENT,
    title VARCHAR(200) NOT NULL,
    englishtitle VARCHAR(200) NOT NULL,
    genre_id INT DEFAULT NULL,
    status_id INT DEFAULT NULL,
    PRIMARY KEY (book_id),
    UNIQUE KEY (title, englishtitle, genre_id, status_id),
    KEY (genre_id),
    KEY (status_id),
    CONSTRAINT book_ibfk_1 FOREIGN KEY (genre_id) REFERENCES genre(genre_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT book_ibfk_2 FOREIGN KEY (status_id) REFERENCES read_status(status_id) ON DELETE RESTRICT ON UPDATE RESTRICT
);

CREATE TABLE booktoauthor (
    book_id INT NOT NULL,
    author_id INT NOT NULL,
    PRIMARY KEY (book_id, author_id),
    KEY (author_id),
    CONSTRAINT booktoauthor_ibfk_1 FOREIGN KEY (author_id) REFERENCES author(author_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT booktoauthor_ibfk_2 FOREIGN KEY (book_id) REFERENCES book(book_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE review (
    book_id INT NOT NULL,
    review_number INT NOT NULL,
    rating INT NOT NULL,
    notes VARCHAR(1000) DEFAULT NULL,
    PRIMARY KEY (book_id, review_number),
    CONSTRAINT review_ibfk_1 FOREIGN KEY (book_id) REFERENCES book(book_id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- TRIGGERS

DROP TRIGGER IF EXISTS prevent_delete_reviewed_book;
DELIMITER $$
CREATE TRIGGER prevent_delete_reviewed_book 
BEFORE DELETE ON book 
FOR EACH ROW
BEGIN
    DECLARE review_count INT;
    SELECT COUNT(*) INTO review_count 
    FROM review 
    WHERE book_id = OLD.book_id;
    
    IF review_count > 0 THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Cannot delete book with reviews. Delete reviews first.';
    END IF;
END$$
DELIMITER ;

DROP TRIGGER IF EXISTS rating_check;
DELIMITER $$
CREATE TRIGGER rating_check 
BEFORE INSERT ON review 
FOR EACH ROW
BEGIN
    IF NEW.rating NOT BETWEEN 1 AND 5 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'rating must between 1 and 5';
    END IF;
END$$
DELIMITER ;

DROP TRIGGER IF EXISTS rating_check_update;
DELIMITER $$
CREATE TRIGGER rating_check_update 
BEFORE UPDATE ON review 
FOR EACH ROW
BEGIN
    IF NEW.rating NOT BETWEEN 1 AND 5 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'rating must between 1 and 5';
    END IF;
END$$
DELIMITER ;

-- STORED PROCEDURES

DROP PROCEDURE IF EXISTS add_book;
DELIMITER $$
CREATE PROCEDURE add_book(
    title_in VARCHAR(200),
    englishtitle_in VARCHAR(200),
    genre_id_in INT,
    status_id_in INT,
    author_name_in VARCHAR(120)
)
BEGIN
    IF NOT EXISTS (SELECT * FROM genre WHERE genre_id = genre_id_in) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'your genre id is not valid';
    END IF;
    
    IF NOT EXISTS (SELECT * FROM read_status WHERE status_id = status_id_in) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'your status id is not valid';
    END IF;
    
    INSERT INTO author(name) SELECT author_name_in
    WHERE NOT EXISTS (SELECT * FROM author WHERE name = author_name_in);
    
    SELECT author_id INTO @aid FROM author WHERE name = author_name_in LIMIT 1;
    
    INSERT INTO book(title, englishtitle, genre_id, status_id) 
    VALUES (title_in, englishtitle_in, genre_id_in, status_id_in);
    
    SET @bid = LAST_INSERT_ID();
    
    INSERT INTO booktoauthor(book_id, author_id) VALUES (@bid, @aid);
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS add_book_by_names;
DELIMITER $$
CREATE PROCEDURE add_book_by_names(
    title_in VARCHAR(200),
    englishtitle_in VARCHAR(200),
    genre_name_in VARCHAR(60),
    status_name_in VARCHAR(40),
    author_name_in VARCHAR(120)
)
BEGIN
    DECLARE genre_id_in INT;
    DECLARE status_id_in INT;
    DECLARE author_id_in INT;
    DECLARE book_id_in INT;
    
    SELECT genre_id INTO genre_id_in FROM genre
    WHERE name = genre_name_in LIMIT 1;
    IF genre_id_in IS NULL THEN 
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'your genre name doesnt exist';
    END IF;
    
    SELECT status_id INTO status_id_in FROM read_status
    WHERE name = status_name_in LIMIT 1;
    IF status_id_in IS NULL THEN 
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'your status doesnt exist';
    END IF;
    
    INSERT INTO author(name) SELECT author_name_in
    WHERE NOT EXISTS (SELECT * FROM author WHERE name = author_name_in);
    
    SELECT author_id INTO author_id_in FROM author 
    WHERE name = author_name_in LIMIT 1;
    
    INSERT INTO book(title, englishtitle, genre_id, status_id) 
    VALUES (title_in, englishtitle_in, genre_id_in, status_id_in);
    SET book_id_in = LAST_INSERT_ID();
    
    INSERT INTO booktoauthor(book_id, author_id) VALUES (book_id_in, author_id_in);
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS add_review;
DELIMITER $$
CREATE PROCEDURE add_review(
    book_id_in INT,
    rating_in INT,
    notes_in VARCHAR(1000)
)
BEGIN
    DECLARE next_review_num INT;
    
    IF NOT EXISTS (SELECT * FROM book WHERE book_id = book_id_in) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Book does not exist';
    END IF;
    
    SELECT IFNULL(MAX(review_number), 0) + 1 INTO next_review_num
    FROM review
    WHERE book_id = book_id_in;
    
    INSERT INTO review(book_id, review_number, rating, notes)
    VALUES (book_id_in, next_review_num, rating_in, notes_in);
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS delete_book;
DELIMITER $$
CREATE PROCEDURE delete_book(book_id_in INT)
BEGIN
    IF NOT EXISTS (SELECT * FROM book WHERE book_id = book_id_in) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Book does not exist';
    END IF;
    
    DELETE FROM book WHERE book_id = book_id_in;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS get_all_book_detail;
DELIMITER $$
CREATE PROCEDURE get_all_book_detail()
BEGIN
    SELECT 
        b.book_id,
        b.title,
        b.englishtitle,
        g.name AS genre,
        rs.name AS status,
        a.name AS author
    FROM book b
    LEFT JOIN genre g ON b.genre_id = g.genre_id
    LEFT JOIN read_status rs ON b.status_id = rs.status_id
    LEFT JOIN booktoauthor ba ON b.book_id = ba.book_id
    LEFT JOIN author a ON ba.author_id = a.author_id
    ORDER BY b.book_id;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS get_all_review;
DELIMITER $$
CREATE PROCEDURE get_all_review()
BEGIN
    SELECT  
        r.book_id,
        b.title,
        b.englishtitle,
        r.review_number,
        r.rating,
        r.notes
    FROM review r
    JOIN book b ON r.book_id = b.book_id
    ORDER BY r.book_id, r.review_number;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS get_book_detail;
DELIMITER $$
CREATE PROCEDURE get_book_detail(book_id_in INT)
BEGIN
    SELECT 
        b.book_id,
        b.title,
        b.englishtitle,
        g.name AS genre,
        rs.name AS status,
        a.name AS author
    FROM book b
    LEFT JOIN genre g ON b.genre_id = g.genre_id
    LEFT JOIN read_status rs ON b.status_id = rs.status_id
    LEFT JOIN booktoauthor ba ON b.book_id = ba.book_id
    LEFT JOIN author a ON ba.author_id = a.author_id
    WHERE b.book_id = book_id_in
    LIMIT 1;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS get_review_detail_by_bookid;
DELIMITER $$
CREATE PROCEDURE get_review_detail_by_bookid(book_id_in INT)
BEGIN
    SELECT  
        b.book_id,
        b.title,
        b.englishtitle,
        r.review_number,
        r.rating,
        r.notes
    FROM review r
    JOIN book b ON r.book_id = b.book_id
    WHERE b.book_id = book_id_in
    ORDER BY review_number;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS search_books;
DELIMITER $$
CREATE PROCEDURE search_books(keyword VARCHAR(200))
BEGIN
    SELECT 
        b.book_id,
        b.title,
        b.englishtitle,
        g.name AS genre,
        rs.name AS status,
        a.name AS authors
    FROM book b
    LEFT JOIN genre g ON b.genre_id = g.genre_id
    LEFT JOIN read_status rs ON b.status_id = rs.status_id
    LEFT JOIN booktoauthor ba ON b.book_id = ba.book_id
    LEFT JOIN author a ON ba.author_id = a.author_id
    WHERE b.title LIKE CONCAT('%', keyword, '%')
       OR b.englishtitle LIKE CONCAT('%', keyword, '%');
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS search_books_by_author;
DELIMITER $$
CREATE PROCEDURE search_books_by_author(author_name_in VARCHAR(120))
BEGIN
    SELECT 
        b.book_id,
        b.title,
        b.englishtitle,
        g.name AS genre,
        rs.name AS status
    FROM book b
    JOIN booktoauthor ba ON b.book_id = ba.book_id
    JOIN author a ON ba.author_id = a.author_id
    LEFT JOIN genre g ON b.genre_id = g.genre_id
    LEFT JOIN read_status rs ON b.status_id = rs.status_id
    WHERE a.name LIKE CONCAT('%', author_name_in, '%')  
    ORDER BY b.book_id;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS update_book_status;
DELIMITER $$
CREATE PROCEDURE update_book_status(
    book_id_in INT,
    status_id_in INT
)
BEGIN
    IF NOT EXISTS (SELECT * FROM book WHERE book_id = book_id_in) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Book does not exist';
    END IF;
    
    IF NOT EXISTS (SELECT * FROM read_status WHERE status_id = status_id_in) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid status id';
    END IF;
    
    UPDATE book 
    SET status_id = status_id_in 
    WHERE book_id = book_id_in;
END$$
DELIMITER ;



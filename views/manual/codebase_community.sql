-- Views thu cong cho database codebase_community (Paper V-SQL style)

-- 1. View ket hop bai dang (posts) va tac gia (users)
CREATE VIEW v_post_user AS
SELECT
    posts.Id AS post_id,
    posts.PostTypeId AS post_type_id,
    posts.Score AS post_score,
    posts.ViewCount AS view_count,
    posts.Title AS post_title,
    posts.Tags AS post_tags,
    posts.AnswerCount AS answer_count,
    posts.CommentCount AS comment_count,
    posts.FavoriteCount AS favorite_count,
    users.Id AS user_id,
    users.DisplayName AS author_name,
    users.Reputation AS author_reputation,
    users.Location AS author_location,
    users.Views AS author_views,
    users.UpVotes AS author_upvotes,
    users.DownVotes AS author_downvotes
FROM posts
LEFT JOIN users ON posts.OwnerUserId = users.Id;

-- 2. View binh luan kem thong tin post va nguoi binh luan
CREATE VIEW v_comment_details AS
SELECT
    comments.Id AS comment_id,
    comments.Score AS comment_score,
    comments.Text AS comment_text,
    comments.CreationDate AS comment_date,
    posts.Id AS post_id,
    posts.Title AS post_title,
    users.Id AS user_id,
    users.DisplayName AS commenter_name,
    users.Reputation AS commenter_reputation
FROM comments
LEFT JOIN posts ON comments.PostId = posts.Id
LEFT JOIN users ON comments.UserId = users.Id;

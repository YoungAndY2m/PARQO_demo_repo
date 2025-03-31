SELECT MIN(mi_idx.info) AS rating,
       MIN(t.title) AS western_dark_production
FROM info_type AS it1,
     info_type AS it2,
     keyword AS k,
     kind_type AS kt,
     movie_info AS mi,
     movie_info_idx AS mi_idx,
     movie_keyword AS mk,
     title AS t
WHERE it1.info = 'countries'
  AND it2.info = 'rating'
  AND (k.keyword = 'murder'
       OR k.keyword = 'murder-in-title')
  AND kt.kind = 'movie'
  AND (mi.info = 'Sweden'
       OR mi.info = 'Norway'
       OR mi.info = 'Germany'
       OR mi.info = 'Denmark'
       OR mi.info = 'Swedish'
       OR mi.info = 'Danish'
       OR mi.info = 'Norwegian'
       OR mi.info = 'German'
       OR mi.info = 'USA'
       OR mi.info = 'American')
  AND mi_idx.info > '6.0'
  AND t.production_year > 2010
  AND (t.title LIKE '%murder%'
       OR t.title LIKE '%Murder%'
       OR t.title LIKE '%Mord%')
  AND kt.id = t.kind_id
  AND t.id = mi.movie_id
  AND t.id = mk.movie_id
  AND t.id = mi_idx.movie_id
  AND mk.movie_id = mi.movie_id
  AND mk.movie_id = mi_idx.movie_id
  AND mi.movie_id = mi_idx.movie_id
  AND k.id = mk.keyword_id
  AND it1.id = mi.info_type_id
  AND it2.id = mi_idx.info_type_id;

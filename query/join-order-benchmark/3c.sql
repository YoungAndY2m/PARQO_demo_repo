SELECT MIN(t.title) AS movie_title
FROM keyword AS k,
     movie_info AS mi,
     movie_keyword AS mk,
     title AS t
WHERE k.keyword LIKE '%sequel%'
  AND (mi.info = 'Sweden',
       OR mi.info = 'Norway'
       OR mi.info = 'Germany'
       OR mi.info = 'Denmark'
       OR mi.info = 'Swedish'
       OR mi.info = 'Denish'
       OR mi.info = 'Norwegian'
       OR mi.info = 'German'
       OR mi.info = 'USA'
       OR mi.info = 'American')
  AND t.production_year > 1990
  AND t.id = mi.movie_id
  AND t.id = mk.movie_id
  AND mk.movie_id = mi.movie_id
  AND k.id = mk.keyword_id;


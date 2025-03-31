SELECT MIN(k.keyword) AS movie_keyword,
       MIN(n.name) AS actor_name,
       MIN(t.title) AS hero_movie
FROM cast_info AS ci,
     keyword AS k,
     movie_keyword AS mk,
     name AS n,
     title AS t
WHERE (k.keyword = 'superhero'
      OR k.keyword = 'sequel'
      OR k.keyword = 'second-part'
      OR k.keyword = 'marvel-comics'
      OR k.keyword = 'based-on-comic'
      OR k.keyword = 'tv-special'
      OR k.keyword = 'fight'
      OR k.keyword = 'violence')
  AND n.name LIKE '%Downey%Robert%'
  AND t.production_year > 2000
  AND k.id = mk.keyword_id
  AND t.id = mk.movie_id
  AND t.id = ci.movie_id
  AND ci.movie_id = mk.movie_id
  AND n.id = ci.person_id;


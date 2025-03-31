SELECT MIN(mi.info) AS movie_budget,
       MIN(mi_idx.info) AS movie_votes,
       MIN(n.name) AS writer,
       MIN(t.title) AS complete_violent_movie
FROM complete_cast AS cc,
     comp_cast_type AS cct1,
     comp_cast_type AS cct2,
     cast_info AS ci,
     info_type AS it1,
     info_type AS it2,
     keyword AS k,
     movie_info AS mi,
     movie_info_idx AS mi_idx,
     movie_keyword AS mk,
     name AS n,
     title AS t
WHERE cct1.kind = 'cast'
  AND cct2.kind = 'complete+verified'
  AND (ci.note = '(writer)' OR
       ci.note = '(head writer)' OR
       ci.note = '(written by)' OR
       ci.note = '(story)' OR
       ci.note = '(story editor)')
  AND it1.info = 'genres'
  AND it2.info = 'votes'
  AND (k.keyword = 'murder' OR
       k.keyword = 'violence' OR
       k.keyword = 'blood' OR
       k.keyword = 'gore' OR
       k.keyword = 'death' OR
       k.keyword = 'female-nudity' OR
       k.keyword = 'hospital')
  AND (mi.info = 'Horror' OR
       mi.info = 'Action' OR
       mi.info = 'Sci-Fi' OR
       mi.info = 'Thriller' OR
       mi.info = 'Crime' OR
       mi.info = 'War')
  AND n.gender = 'm'
  AND t.id = mi.movie_id
  AND t.id = mi_idx.movie_id
  AND t.id = ci.movie_id
  AND t.id = mk.movie_id
  AND t.id = cc.movie_id
  AND ci.movie_id = mi.movie_id
  AND ci.movie_id = mi_idx.movie_id
  AND ci.movie_id = mk.movie_id
  AND ci.movie_id = cc.movie_id
  AND mi.movie_id = mi_idx.movie_id
  AND mi.movie_id = mk.movie_id
  AND mi.movie_id = cc.movie_id
  AND mi_idx.movie_id = mk.movie_id
  AND mi_idx.movie_id = cc.movie_id
  AND mk.movie_id = cc.movie_id
  AND n.id = ci.person_id
  AND it1.id = mi.info_type_id
  AND it2.id = mi_idx.info_type_id
  AND k.id = mk.keyword_id
  AND cct1.id = cc.subject_id
  AND cct2.id = cc.status_id;

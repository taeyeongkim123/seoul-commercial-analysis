-- TODO: 실제 컬럼명 확인 후 명시적 select + rename 하도록 교체할 것.
select * from {{ source('raw', 'raw_change_index') }}

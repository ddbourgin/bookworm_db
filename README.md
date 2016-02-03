# bookworm_db
Modifications to database construction scripts. Forked from https://github.com/Bookworm-project/BookwormDB

##TODO:
1. Modify `tokenizer.py` for phoneme tokenization. We should not separate letters and numbers here (e.g., `AH0` should not be treated as two tokens)
2. Add code for creating pause and word:pronunciation tables to `CreateDatabase.py`

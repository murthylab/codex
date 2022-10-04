open http://localhost:5000/ && \
export FLASK_APP=src.main && \
export FLASK_SECRET_KEY=dev_dummy_key && \
export SMOKE_TEST_KEY=dev_smoke_test_key && \
export BUILD_GIT_SHA=`git log | head -1 | cut -d " " -f 2` && \
export BUILD_TIMESTAMP=`date` &&\
flask run
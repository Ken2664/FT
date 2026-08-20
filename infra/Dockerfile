# 実験イメージ。infra/RUNPOD.md §6「環境の固定」。
#
# ベースタグは **実在を確認してから** 書くこと。
# RunPod のイメージ一覧を実際に見て、使うタグを固定する。
# 未確認のタグを書くと、ビルドが通らないか、通っても別環境になる。
#
#   docker build -f infra/Dockerfile -t translesion:<日付> .
#   docker push <registry>/translesion:<日付>
#
# タグは日付で固定し、latest を使わない。latest は再現性を壊す。

ARG BASE_IMAGE=runpod/pytorch:UNPINNED-未確認
FROM ${BASE_IMAGE}

# ロックファイルからのみ入れる。--no-deps で解決を再走させない
# (infra/RUNPOD.md §6「`>=` を使わない」)。
COPY infra/requirements.lock /tmp/requirements.lock
RUN pip install --no-deps -r /tmp/requirements.lock

WORKDIR /workspace/translesion
COPY . .

# ビルド時点で環境が壊れていないことを確認する。
# ここで落ちればポッドを起動する前に気づける。
RUN python -m pytest code/tests -q

# コンテナに入った直後に preflight を促す。
CMD ["bash", "-lc", "echo '次: python infra/preflight.py --config configs/<実験>.yaml'; exec bash"]

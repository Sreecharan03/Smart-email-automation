#!/bin/bash
# for dev

if [ "$MARSCODE_DEV_MODE" ]; then
    # chmod +x ./binary/ckg_server_darwin_arm64
    if [ "$MARSCODE_DEV_AI_AGENT_MANUAL" ]; then
        sleep 9999999
    else
        # 设置默认值
        if [ -z "$AI_NATIVE_ENV" ]; then
            AI_NATIVE_ENV=desktop
        fi
        if [ -z "$RUST_LOG" ]; then
            RUST_LOG=INFO
        fi

        export AI_NATIVE_ENV=$AI_NATIVE_ENV
        export RUST_LOG=$RUST_LOG
        export TTNET_LIB_DIR_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deps/ttnet/macos/m1"
        export RUST_LOG=INFO
        export CLOUDIDE_TENANT_NAME=cn
        export ICUBE_MODULAR_DATA_DIR=$HOME/.icube
        export DB_PATH=$ICUBE_MODULAR_DATA_DIR/ai-agent/database.db
        export FILE_BASE_DIR=$ICUBE_MODULAR_DATA_DIR/ai-agent/snapshot
        cargo run
    fi
else
    if [ "$TRAE_RESOLVE_TYPE" = "remote" ]; then
        export AI_NATIVE_ENV=plugin_remote
    elif [ "$TRAE_RESOLVE_TYPE" = "ssh" ]; then
        export AI_NATIVE_ENV=desktop_ssh
    fi
    export DB_PATH=$ICUBE_MODULAR_DATA_DIR/ai-agent/database.db
    export FILE_BASE_DIR=$ICUBE_MODULAR_DATA_DIR/ai-agent/snapshot
    exec ./ai-agent
fi

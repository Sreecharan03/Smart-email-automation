#!/bin/bash
# for dev

if [ "$MARSCODE_DEV_MODE" ]; then
    chmod +x ./binary/ckg_server_darwin_arm64
    if [ "$MARSCODE_DEV_CKG_MANUAL" ]; then
        sleep 9999999
    else
        export AI_NATIVE_ENV=desktop
        export RUST_LOG=INFO
        export CLOUDIDE_TENANT_NAME=cn
        export ICUBE_MODULAR_DATA_DIR=$HOME/.icube
        export DB_PATH=$ICUBE_MODULAR_DATA_DIR/ai-chat/database.db
        export FILE_BASE_DIR=$ICUBE_MODULAR_DATA_DIR/ai-chat/snapshot

        ARCH=arm64 node ./rust-ai-ckg.mjs

        # 设置默认值
        if [ -z "$CKG_APP_ID" ]; then
            CKG_APP_ID="6eefa01c-1036-4c7e-9ca5-d891f63bfcd8"
        fi
        if [ -z "$CKG_SOURCE_PRODUCT" ]; then
            CKG_SOURCE_PRODUCT="native_ide"
        fi

        ./binary/ckg_server -port=${PORT0} -ide_version=${ICUBE_BUILD_VERSION} -version_code=2 -storage_path="$ICUBE_MODULAR_DATA_DIR/ckg_server" -local_embedding -embedding_storage_type=sqlite_vec -app_id=$CKG_APP_ID -limit_cpu=1 -source_product=$CKG_SOURCE_PRODUCT
    fi
else
    # 优先检查 AI_NATIVE_ENV 是否为 plugin
    if [ "$AI_NATIVE_ENV" = "plugin" ] || [ "$AI_NATIVE_ENV" = "plugin_boe" ]; then
        if [ "$TRAE_RESOLVE_TYPE" = "remote" ]; then
            export AI_NATIVE_ENV=plugin_remote
        else
            export AI_NATIVE_ENV=plugin
        fi
    elif [ "$ICUBE_PRODUCT_TYPE" = "desktop" ]; then
        if [ "$TRAE_RESOLVE_TYPE" = "ssh" ]; then
            export AI_NATIVE_ENV=desktop_ssh
        else
            export AI_NATIVE_ENV=desktop
        fi
    elif [ "$CLOUDIDE_TENANT_NAME" = "bytedance" ]; then
        export AI_NATIVE_ENV=cloudide
    elif [ "$CLOUDIDE_PROJECT_SCENE" = "practice" ]; then
        export AI_NATIVE_ENV=practice
    elif [ "$CLOUDIDE_PROVIDER_REGION" = "cn" ]; then
        export AI_NATIVE_ENV=marscode_boe
    elif [ "$CLOUDIDE_PROVIDER_REGION" = "us" ]; then
        export AI_NATIVE_ENV=marscode_boei18n
    elif [ "$CLOUDIDE_PROVIDER_REGION" = "sg" ]; then
        export AI_NATIVE_ENV=marscode_boei18n
    else
        export AI_NATIVE_ENV=marscode_boe
    fi
    export DB_PATH=$ICUBE_MODULAR_DATA_DIR/ai-chat/database.db
    export FILE_BASE_DIR=$ICUBE_MODULAR_DATA_DIR/ai-chat/snapshot

    # 设置默认值
    if [ -z "$CKG_APP_ID" ]; then
        CKG_APP_ID="6eefa01c-1036-4c7e-9ca5-d891f63bfcd8"
    fi
    if [ -z "$CKG_SOURCE_PRODUCT" ]; then
        CKG_SOURCE_PRODUCT="native_ide"
    fi

    # 如果设置了 PLUGIN_IDE_TYPE，添加 --ideType 参数
    IDE_TYPE_ARG=""
    if [ -n "$PLUGIN_IDE_TYPE" ]; then
        IDE_TYPE_ARG="--ideType=${PLUGIN_IDE_TYPE}"
    fi

    exec ./binary/ckg_server -port=${PORT0} -ide_version=${ICUBE_BUILD_VERSION} -version_code=2 -storage_path="$ICUBE_MODULAR_DATA_DIR/ckg_server" -local_embedding -embedding_storage_type=sqlite_vec -app_id=$CKG_APP_ID -limit_cpu=1 -source_product=$CKG_SOURCE_PRODUCT $IDE_TYPE_ARG
fi

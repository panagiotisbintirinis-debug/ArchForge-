from archforge.ui.pbr_viewport import is_benign_console_message


def test_direct3d_compiler_warning_is_kept_out_of_the_console():
    msg = ("THREE.WebGLProgram: Program Info Log: C:\\fakepath(100,1-6): warning X4000: use of potentially "
           "uninitialized variable (dyn_index_vec4_float4_int)")
    assert is_benign_console_message(msg)


def test_real_errors_and_other_messages_still_show():
    assert not is_benign_console_message("THREE.WebGLProgram: Shader Error 1282 - VALIDATE_STATUS false ... error X3004")
    assert not is_benign_console_message("Uncaught TypeError: cannot read properties of undefined")
    assert not is_benign_console_message("ArchForge scene ready")

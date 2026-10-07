"""E 段的显卡材质。导入本模块即完成注册。

门这一侧（L19）的材质都按同一盏马灯算光：灯在门前约 9 厘米，光强按距离平方衰减（L_r0 为衰减到一半的距离），
照到门面上的强弱还取决于入射角，所以离灯越远光越斜，木纹的沟坎越明显；马灯的灯帽挡住往上的光、油壶挡住往下的光，
灯的正上方和正下方各有一片暗区，这是马灯真实的光形。锁孔透出另一边的冷青色光时，锁孔周围另加一圈青光（K_glow）。

水下（L20–L22）的材质按"水深"和"离镜头的距离"上色：越深越暗，越远越融进水色；水面下方的光柱和焦散纹由时间驱动，
分段渲染时结果一致。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import register_material  # noqa: E402

LAMP = """
uniform vec3 L_pos;        // 火苗的世界坐标
uniform vec3 L_col;        // 灯光颜色（已含强度）
uniform float L_r0;        // 衰减到一半的距离
uniform vec3 L_amb;        // 环境里极弱的冷光
uniform vec4 K_glow;       // 锁孔透出的光：(x, y, 半径, 强度)
uniform vec3 K_col;

float lamp_block(vec3 d) {
    float elev = atan(d.y, max(length(d.xz), 1e-4));
    float cap = 1.0 - 0.90 * smoothstep(0.55, 1.05, elev);
    float tank = 1.0 - 0.92 * smoothstep(0.80, 1.25, -elev);
    return cap * tank;
}
vec3 lamp_light(vec3 p, vec3 n) {
    vec3 d = p - L_pos;
    float r2 = dot(d, d);
    vec3 Ld = -d * inversesqrt(r2 + 1e-8);
    float ndl = max(dot(n, Ld), 0.0);
    float fall = 1.0 / (1.0 + r2 / (L_r0 * L_r0));
    return L_col * (fall * mix(0.30, 1.0, ndl) * (0.55 + 0.45 * ndl / max(Ld.z, 0.15)) * lamp_block(d));
}
vec3 key_light(vec3 p) {
    float r = length(p.xy - K_glow.xy);
    return K_col * K_glow.w * (exp(-r / K_glow.z) + 0.35 * exp(-r / (K_glow.z * 4.0)));
}
"""

# 门面、搭扣、锁片：反照率乘灯光；bump 为高度图（亮度的高频部分），用来求出近似法线
register_material("e_lit", LAMP + """
uniform sampler2D bump;
uniform float bump_k;
uniform float has_bump;
vec4 material(vec4 base) {
    if (base.a <= 0.0) return base;
    vec3 alb = base.rgb / base.a;
    vec3 n = vec3(0.0, 0.0, 1.0);
    if (has_bump > 0.5) {
        vec2 px = 1.0 / vec2(textureSize(bump, 0));
        float lod = max(log2(max(length(fwidth(v_uv) / px), 1.0)), 0.0);
        vec2 o = px * exp2(lod);
        float hx = textureLod(bump, v_uv + vec2(o.x, 0.0), lod).r - textureLod(bump, v_uv - vec2(o.x, 0.0), lod).r;
        float hy = textureLod(bump, v_uv - vec2(0.0, o.y), lod).r - textureLod(bump, v_uv + vec2(0.0, o.y), lod).r;
        n = normalize(vec3(-hx * bump_k, -hy * bump_k, 1.0));
    }
    vec3 light = lamp_light(v_wpos, n) + L_amb + key_light(v_wpos);
    return vec4(alb * light * base.a, base.a);
}
""", defaults={"L_pos": (0.0, 0.0, 0.1), "L_col": (1.0, 0.7, 0.4), "L_r0": 0.4, "L_amb": (0.01, 0.012, 0.016),
               "K_glow": (0.0, 0.0, 0.01, 0.0), "K_col": (0.3, 0.9, 1.0), "bump_k": 3.0, "has_bump": 0.0})

# 门上的粉笔字：字形覆盖率在粗糙的木面上断断续续（干粉笔擦过木纹的凸处才留下粉），亮度同样取决于灯光；
# reveal 从 0 到 1 时字从上往下被写出，前沿带一点不规则
register_material("e_chalk", LAMP + """
uniform float reveal;
uniform float chalk_k;
uniform float chalk_gain;
vec4 material(vec4 base) {
    if (base.a <= 0.0) return base;
    vec3 col = base.rgb / base.a;
    vec2 q = v_local;
    float g = vnoise(q * 1400.0, 7) * 0.55 + vnoise(q * 420.0, 8) * 0.30 + vnoise(vec2(q.x * 60.0, q.y * 900.0), 9) * 0.15;
    float dry = mix(1.0, smoothstep(0.18, 0.62, g), chalk_k);
    float edge = v_uv01.y + 0.18 * (vnoise(q * 90.0, 10) - 0.5);
    float m = smoothstep(edge - 0.02, edge + 0.10, reveal * 1.25);
    // 粉笔是白的：亮度跟着灯光走，颜色保持暖白（只取灯光的亮度，不取它的橙色）
    vec3 light = lamp_light(v_wpos, vec3(0.0, 0.0, 1.0)) + L_amb;
    float lum = dot(light, vec3(0.30, 0.55, 0.15));
    vec3 lit = col * (lum * chalk_gain) + key_light(v_wpos) * 0.6;
    float a = base.a * dry * m;
    return vec4(lit * a, a);
}
""", defaults={"L_pos": (0.0, 0.0, 0.1), "L_col": (1.0, 0.7, 0.4), "L_r0": 0.4, "L_amb": (0.01, 0.012, 0.016),
               "K_glow": (0.0, 0.0, 0.01, 0.0), "K_col": (0.3, 0.9, 1.0), "reveal": 1.0, "chalk_k": 0.8,
               "chalk_gain": 1.6})

# 锁孔的孔道：一圈圈挖了锁孔形洞的薄片，深处被另一边的青光照亮（depth01：0 为入口，1 为出口）
register_material("e_tunnel", """
uniform float depth01;
uniform vec3 tun_warm;
uniform vec3 tun_cold;
vec4 material(vec4 base) {
    float n = vnoise(v_local * 3000.0, 21) * 0.5 + vnoise(v_local * 800.0, 22) * 0.5;
    vec3 c = mix(tun_warm, tun_cold, depth01 * depth01) * (0.7 + 0.6 * n);
    return vec4(c * base.a, base.a);
}
""", defaults={"depth01": 0.0, "tun_warm": (0.05, 0.035, 0.02), "tun_cold": (0.10, 0.35, 0.40)})

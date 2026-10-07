"""副歌一样片用到的显卡材质。导入本模块即完成注册。

铁水的颜色按温度取：冷却后的暗红 → 橙 → 黄白，与样张 B 的铁水一致（数值超过 1 的部分由过去的调色加上橙色光晕）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import register_material  # noqa: E402

MOLTEN = """
vec3 molten(float T) {
    vec3 hot = vec3(2.4, 1.75, 0.95), mid = vec3(1.75, 0.62, 0.12), cold = vec3(0.42, 0.07, 0.03);
    return T > 0.6 ? mix(mid, hot, clamp((T - 0.6) / 0.4, 0.0, 1.0)) : mix(cold, mid, clamp((T - 0.22) / 0.38, 0.0, 1.0));
}
"""

# 桌面：木纹 + L08 凹槽（刻出后带斜面明暗，灌铁水后发光）+ L09 逐字烧穿
register_material("desk_c", MOLTEN + """
uniform sampler2D aux;
uniform sampler2D glowmap;
uniform float t_base;
uniform float night;
uniform float glow_fill;
uniform float glow_burn;
uniform vec3 day_light;
uniform vec3 night_light;
uniform float carve_t0;
uniform float carve_span;

vec4 material(vec4 base) {
    float t = u_time - t_base;
    vec4 a = texture(aux, v_uv);
    vec4 gl = texture(glowmap, v_uv);
    vec2 px = 1.0 / vec2(textureSize(aux, 0));
    float rx = texture(aux, v_uv + vec2(px.x, 0.0)).r - texture(aux, v_uv - vec2(px.x, 0.0)).r;
    float ry = texture(aux, v_uv + vec2(0.0, px.y)).r - texture(aux, v_uv - vec2(0.0, px.y)).r;
    vec3 wood = base.rgb;
    vec3 light = mix(day_light, night_light, night)
               + vec3(1.0, 0.48, 0.18) * (gl.r * glow_fill * 1.2 + gl.g * glow_burn * smoothstep(gl.b, gl.b + 0.3, t) * 1.0);

    // L08 凹槽：刻出之后露出浅色的新木，左上内壁背光、右下内壁受光
    float tc = carve_t0 + carve_span * base.a;
    float carved = smoothstep(tc - 0.03, tc + 0.09, u_time) * a.r;
    float fresh = exp(-max(u_time - tc, 0.0) / 0.45);
    float shade = -(rx + ry) * 0.7071;
    vec3 raw = wood * vec3(1.85, 1.58, 1.22) * (0.70 + 0.9 * shade) * (1.0 + 0.6 * fresh);
    vec3 col = mix(wood, raw, carved) * light;
    // 铁水灌满凹槽：灌到时最亮，之后在一两秒内冷却到橙红
    float fill = smoothstep(a.g, a.g + 0.05, t) * carved;
    float age = max(t - a.g, 0.0);
    float T = 0.38 + 0.62 * exp(-age / 0.9) + 0.06 * (vnoise(v_uv * vec2(88.0, 40.0) + vec2(u_time * 1.7, 0.0), 3) - 0.5);
    col = mix(col, molten(T), fill);

    // L09 烧穿：烧到之前先焦黑、再发红，烧到之后成洞；字外一圈焦痕和余烬
    float db = t - a.a;
    float inside = smoothstep(0.35, 0.65, a.b);
    float scorch = smoothstep(-0.22, -0.02, db);
    col *= 1.0 - 0.8 * scorch;
    float ember = smoothstep(-0.10, 0.0, db) * exp(-max(db, 0.0) / mix(0.22, 0.25, inside));
    float n = vnoise(v_uv * vec2(395.0, 176.0) + u_time * 2.0, 5);
    col += molten(0.28 + 0.4 * ember * (0.5 + 0.5 * n)) * ember * (0.5 + 0.7 * n);
    float hole = smoothstep(0.0, 0.015, db) * inside;
    float alpha = 1.0 - hole;
    return vec4(col * alpha, alpha);
}
""", defaults={"t_base": 50.0, "night": 0.0, "glow_fill": 0.0, "glow_burn": 0.0, "day_light": (1.05, 0.95, 0.8),
               "night_light": (0.15, 0.17, 0.23), "carve_t0": 50.8, "carve_span": 4.0})

# 标语墙：砖与石灰的底色 + 夜光与铁水的暖光 + 从左往右推进的刷白（前沿湿、刷毛纹）+ 红色从白灰下渗出 + 铁水
register_material("wall_c", MOLTEN + """
uniform sampler2D aux1;
uniform sampler2D aux2;
uniform sampler2D warmmap;
uniform float t_base;
uniform float lead_x;
uniform float bleed_p;
uniform float warm_k;
uniform vec3 amb;
uniform float wall_w;

vec4 material(vec4 base) {
    float t = u_time - t_base;
    vec4 a1 = texture(aux1, v_uv);
    vec4 a2 = texture(aux2, v_uv);
    vec4 wm = texture(warmmap, v_uv);
    vec3 alb = base.rgb;

    float wx = v_uv.x * wall_w + a2.r;
    float cover = a1.a * smoothstep(lead_x + 0.04, lead_x - 0.04, wx);
    vec3 fresh = vec3(1.12, 1.11, 1.06) * (0.86 + 0.2 * a2.g);
    float bl = a2.b * smoothstep(a2.a - 0.08, a2.a + 0.02, bleed_p * 1.15);
    fresh = mix(fresh, vec3(0.90, 0.47, 0.40), bl * 0.9);
    float wet = clamp(1.0 - abs(wx - lead_x) / 0.45, 0.0, 1.0) * step(wx, lead_x + 0.05);
    fresh *= 1.0 - 0.22 * wet;
    alb = mix(alb, fresh, cover * (0.78 + 0.22 * a2.g));

    float v = v_uv.y, u = v_uv.x;
    vec3 light = amb * (0.75 + 0.35 * (1.0 - v)) * (1.05 - 0.3 * u) + wm.r * warm_k * vec3(1.0, 0.52, 0.2);
    vec3 col = alb * light;

    float mf = a1.r * smoothstep(a1.g, a1.g + 0.05, t);
    float age = max(t - a1.g, 0.0);
    float T = max(a1.b * 0.85, 0.32 + 0.68 * exp(-age / 1.4)) + 0.05 * (vnoise(v_uv * vec2(380.0, 150.0) + vec2(0.0, -u_time * 3.0), 7) - 0.5);
    col = mix(col, molten(T), mf);
    float hl = smoothstep(wm.b, wm.b + 0.3, t);
    col += wm.g * hl * vec3(1.2, 0.45, 0.12) * 0.9;
    return vec4(col, 1.0);
}
""", defaults={"t_base": 50.0, "lead_x": -1.0, "bleed_p": 0.0, "warm_k": 0.0, "amb": (0.30, 0.34, 0.44), "wall_w": 38.0})

# 歌词逐字写出：字从左往右显出（progress 0→1），刚写出时略亮
register_material("reveal_lr", """
uniform float progress;
uniform float flare;
vec4 material(vec4 base) {
    float m = smoothstep(v_uv01.x, v_uv01.x + 0.12, progress * 1.12);
    return base * m * (1.0 + flare);
}
""", defaults={"progress": 1.0, "flare": 0.0})

# 横幅裂开：crack 贴图 R 为裂纹覆盖率、G 为裂纹前沿到达的时刻（0–1，不在裂纹上为 2），进度 progress 时裂纹处压暗，
# 刚裂开的一段边缘透出一点亮
register_material("banner_crack", """
uniform sampler2D crack;
uniform float progress;
vec4 material(vec4 base) {
    vec4 c = texture(crack, v_uv);
    float on = c.r * step(c.g, progress);
    float fresh = on * exp(-max(progress - c.g, 0.0) * 12.0);
    vec3 col = base.rgb * (1.0 - 0.85 * on) + fresh * base.a * vec3(0.9, 0.5, 0.25);
    return vec4(col, base.a);
}
""", defaults={"progress": 0.0})

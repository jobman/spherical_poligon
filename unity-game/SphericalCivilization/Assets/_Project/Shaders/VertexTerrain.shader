Shader "SphericalCivilization/VertexTerrain"
{
    Properties
    {
        _BorderColor ("Border color", Color) = (0.002, 0.0035, 0.0044, 1)
        _BorderWidth ("Border width (pixels)", Range(0, 4)) = 1
        _SelectionColor ("Selection color", Color) = (1, 0.49, 0.027, 1)
        _AttackTargetColor ("Attack target color", Color) = (1, 0.08, 0.14, 1)
        _SelectionWidth ("Selection width (pixels)", Range(1, 8)) = 3
        [HideInInspector] _SelectedTileId ("Selected tile", Float) = -1
        [HideInInspector] _SelectedSubtileId ("Selected subtile", Float) = -1
        [HideInInspector] _AttackTargetSubtileId ("Attack target subtile", Float) = -1
        [HideInInspector] _SubtileVisibility ("Subtile visibility", Float) = 0
    }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "RenderType"="Opaque" }
        Pass
        {
            Tags { "LightMode"="UniversalForward" }
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma target 3.0
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half4 _BorderColor;
                half4 _SelectionColor;
                half4 _AttackTargetColor;
                float _BorderWidth;
                float _SelectionWidth;
                float _SelectedTileId;
                float _SelectedSubtileId;
                float _AttackTargetSubtileId;
                float _SubtileVisibility;
            CBUFFER_END

            struct Attributes
            {
                float3 positionOS : POSITION;
                float3 normalOS : NORMAL;
                half4 color : COLOR;
                float3 barycentric : TEXCOORD0;
                float4 borders : TEXCOORD1;
                float4 regions : TEXCOORD2;
                float3 parentDistancesA : TEXCOORD3;
                float3 parentDistancesB : TEXCOORD4;
            };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                half3 normalWS : TEXCOORD0;
                half4 color : COLOR;
                float3 barycentric : TEXCOORD1;
                nointerpolation float4 borders : TEXCOORD2;
                nointerpolation float4 regions : TEXCOORD3;
                float3 parentDistancesA : TEXCOORD4;
                float3 parentDistancesB : TEXCOORD5;
            };

            Varyings Vert(Attributes input)
            {
                Varyings output;
                output.positionCS = TransformObjectToHClip(input.positionOS);
                output.normalWS = TransformObjectToWorldNormal(input.normalOS);
                output.color = input.color;
                output.barycentric = input.barycentric;
                output.borders = input.borders;
                output.regions = input.regions;
                output.parentDistancesA = input.parentDistancesA;
                output.parentDistancesB = input.parentDistancesB;
                return output;
            }

            half4 Frag(Varyings input) : SV_Target
            {
                Light sun = GetMainLight();
                half daylight = saturate(dot(normalize(input.normalWS), sun.direction));
                half3 illumination = half3(0.32, 0.38, 0.46) + sun.color * daylight * 0.85;
                // The border is part of the surface fragment, at exactly the same depth.
                // Screen derivatives keep its width stable as the camera zooms or tilts.
                float3 dx = ddx(input.barycentric);
                float3 dy = ddy(input.barycentric);
                float3 edgeDistance = input.barycentric / max(sqrt(dx * dx + dy * dy), 0.000001);
                float3 cellDistance = lerp(float3(100000, 100000, 100000), edgeDistance, input.borders.xyz);
                float cellBorder = min(cellDistance.x, min(cellDistance.y, cellDistance.z));
                // Every fragment knows all of its parent's edge equations. Parent
                // outlines are not clipped to subpixel fan triangles at the horizon.
                float3 parentDxA = ddx(input.parentDistancesA), parentDyA = ddy(input.parentDistancesA);
                float3 parentDxB = ddx(input.parentDistancesB), parentDyB = ddy(input.parentDistancesB);
                float3 parentA = input.parentDistancesA / max(sqrt(parentDxA * parentDxA + parentDyA * parentDyA), 0.00000001);
                float3 parentB = input.parentDistancesB / max(sqrt(parentDxB * parentDxB + parentDyB * parentDyB), 0.00000001);
                float parentBorder = min(min(parentA.x, min(parentA.y, parentA.z)), min(parentB.x, min(parentB.y, parentB.z)));
                half3 terrain = input.color.rgb * illumination;
                bool selectedCell = abs(input.regions.w - _SelectedSubtileId) < 0.5;
                bool attackTarget = abs(input.regions.w - _AttackTargetSubtileId) < 0.5;
                terrain = lerp(terrain, _SelectionColor.rgb, selectedCell * 0.18);
                terrain = lerp(terrain, _AttackTargetColor.rgb, attackTarget * 0.28);
                half fineCoverage = (1.0 - smoothstep(0.0, 0.85, cellBorder)) * _SubtileVisibility;
                terrain = lerp(terrain, terrain * 0.35, fineCoverage);
                bool selected = abs(input.borders.w - _SelectedTileId) < 0.5 &&
                    _SelectedSubtileId < 0.0;
                float width = selected ? _SelectionWidth : _BorderWidth * 0.5;
                half coverage = (1.0 - smoothstep(max(0.0, width - 0.5), width + 0.5, parentBorder)) * (width > 0.0);
                terrain = lerp(terrain, selected ? _SelectionColor.rgb : _BorderColor.rgb, coverage);
                half cellCoverage = (1.0 - smoothstep(_SelectionWidth - 0.5, _SelectionWidth + 0.5, cellBorder)) * (selectedCell || attackTarget);
                return half4(lerp(terrain, attackTarget ? _AttackTargetColor.rgb : _SelectionColor.rgb, cellCoverage), 1.0);
            }
            ENDHLSL
        }
    }
}

Shader "SphericalCivilization/Battlefield"
{
    Properties
    {
        _GridColor ("Hex grid", Color) = (0.36, 0.46, 0.49, 1)
        _SelectedHex ("Selected hex", Float) = -1
    }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "RenderType"="Transparent" "Queue"="Transparent" }
        Pass
        {
            Tags { "LightMode"="SRPDefaultUnlit" }
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Off
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma target 3.0
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            CBUFFER_START(UnityPerMaterial)
                half4 _GridColor;
                float _SelectedHex;
            CBUFFER_END
            struct Attributes { float3 positionOS:POSITION; half4 color:COLOR; float3 barycentric:TEXCOORD0; float2 cell:TEXCOORD1; };
            struct Varyings { float4 positionCS:SV_POSITION; half4 color:COLOR; float3 barycentric:TEXCOORD0; nointerpolation float2 cell:TEXCOORD1; };
            Varyings Vert(Attributes input)
            {
                Varyings output; output.positionCS=TransformObjectToHClip(input.positionOS);
                output.color=input.color; output.barycentric=input.barycentric; output.cell=input.cell; return output;
            }
            half4 Frag(Varyings input):SV_Target
            {
                float2 gradient=float2(ddx(input.barycentric.x),ddy(input.barycentric.x));
                float distance=input.barycentric.x/max(length(gradient),0.000001);
                half edge=(1-smoothstep(0.0,0.85,distance))*input.cell.x;
                half3 color=lerp(input.color.rgb,_GridColor.rgb,edge*0.8);
                if(abs(input.cell.y-_SelectedHex)<0.5 && input.cell.x>0.5) color=lerp(color,half3(0.52,0.42,0.12),0.42);
                return half4(color,input.color.a);
            }
            ENDHLSL
        }
    }
}

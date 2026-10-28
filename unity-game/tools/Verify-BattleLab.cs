// Geometry and persistence through game APIs. No UI control tests or input events.
var lab=UnityEngine.Object.FindFirstObjectByType<SphericalCivilization.Battle.BattlefieldLab>();
void Require(bool value,string message){if(!value)throw new System.Exception(message);}
Require(lab!=null && lab.IsReady,"Battle lab is not ready.");
int original=lab.SizePercent;
string path=System.IO.Path.Combine(UnityEngine.Application.temporaryCachePath,"battle-lab-check-"+System.Guid.NewGuid().ToString("N")+".json");
var reports=new System.Collections.Generic.List<object>();
var previousCounts=new int[]{int.MaxValue,int.MaxValue,int.MaxValue};
var basePolygons=new UnityEngine.Vector2[3][];
for(int i=0;i<3;i++)basePolygons[i]=System.Array.ConvertAll(lab.Fields[i].Regions[0].Polygon,p=>p*lab.Fields[i].WorldHexRadius);
try
{
    foreach(int size in new[]{30,50,100,200,300})
    {
        lab.SetSizePercent(size);
        var counts=new int[3];float radius=lab.GetSettings().hexWorldRadius;
        var pairs=new System.Collections.Generic.HashSet<string>();
        for(int sample=0;sample<3;sample++)
        {
            var f=lab.Fields[sample];counts[sample]=f.CoreHexCount;
            Require(System.Math.Abs(f.WorldHexRadius-radius)<1e-9,"Preview fields use different hex sizes.");
            Require(counts[sample]<previousCounts[sample],"Larger hexes did not reduce the cell count.");previousCounts[sample]=counts[sample];
            Require(pairs.Add(System.Math.Min(f.FirstSubtileIndex,f.SecondSubtileIndex)+":"+System.Math.Max(f.FirstSubtileIndex,f.SecondSubtileIndex)),"Duplicate lab sample pair.");
            Require(f.Units.Count==2 && f.Units[0].HexIndex!=f.Units[1].HexIndex,"Test token placement failed at this density.");
            for(int v=0;v<basePolygons[sample].Length;v++)
                Require((f.Regions[0].Polygon[v]*radius-basePolygons[sample][v]).sqrMagnitude<1e-12,"Changing hex size resized the geography.");
            var rows=new int[4];
            for(int i=0;i<f.Hexes.Count;i++)
            {
                var h=f.Hexes[i];rows[h.RetreatRow]++;
                Require(h.IsEscape==(h.RetreatRow==3),"Escape threshold changed with density.");
                foreach(int n in h.Neighbors)if(n>=0)Require(System.Array.IndexOf(f.Hexes[n].Neighbors,i)>=0,"Non-reciprocal tactical neighbors.");
            }
            foreach(int count in rows)Require(count>0,"Missing core or retreat row.");
        }
        reports.Add(new{sizePercent=size,radius,coreCounts=counts,milliseconds=lab.LastGenerationMilliseconds});
    }
    lab.SetSizePercent(165);lab.SaveSettings(path);
    Require(SphericalCivilization.Battle.BattleSettingsStore.TryLoad(path,out var saved),"Cannot read saved battle settings.");
    Require(saved.hexWorldRadius==lab.GetSettings().hexWorldRadius,"Save/load changed the radius.");
    var chosen=lab.Samples[0];
    var regular=SphericalCivilization.Battle.Battlefield.Build(lab.World,chosen.First,chosen.Second,.73f,hexWorldRadius:saved.hexWorldRadius);
    Require(regular.WorldHexRadius==lab.Fields[0].WorldHexRadius && regular.CoreHexCount==lab.Fields[0].CoreHexCount,"Saved size generates a different regular battlefield.");
    lab.SetSizePercent(200);lab.SaveSettings(path);
    Require(SphericalCivilization.Battle.BattleSettingsStore.TryLoad(path,out var replaced) && replaced.hexWorldRadius==lab.GetSettings().hexWorldRadius,"Replacing an existing settings file failed.");
    System.IO.File.WriteAllText(path,"{\"hexWorldRadius\":-1}");
    Require(!SphericalCivilization.Battle.BattleSettingsStore.TryLoad(path,out _),"Invalid persisted radius accepted.");
    bool rejected=false;
    try{SphericalCivilization.Battle.BattleSettingsStore.Save(path,new SphericalCivilization.Battle.BattleSettings{hexWorldRadius=float.NaN});}catch(System.ArgumentOutOfRangeException){rejected=true;}
    Require(rejected,"Non-finite radius accepted.");
    return new{result="PASS",samples=lab.Samples.Count,commonScale=true,persistence=true,regularBattleMatchesPreview=true,checks=reports};
}
finally{lab.SetSizePercent(original);if(System.IO.File.Exists(path))System.IO.File.Delete(path);}

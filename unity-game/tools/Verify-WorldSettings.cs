// Data and file checks only; does not operate UI or change saved user settings.
string directory=System.IO.Path.Combine(System.IO.Path.GetTempPath(),"SphericalWorldSettings-"+System.Guid.NewGuid());
string path=System.IO.Path.Combine(directory,"WorldSettings.json");
void Require(bool ok,string message){if(!ok)throw new System.Exception(message);}
try
{
    Require(!SphericalCivilization.WorldSettingsStore.TryLoad(path,out var absent),"Missing settings should use scene defaults.");
    foreach(int count in new[]{12,37,128})
    {
        SphericalCivilization.WorldSettingsStore.Save(path,new SphericalCivilization.WorldSettings{subtilesPerTile=count,seed=42});
        Require(SphericalCivilization.WorldSettingsStore.TryLoad(path,out var settings) && settings.subtilesPerTile==count && settings.seed==42 &&
            settings.hexagonSubtilesPerTile==count && settings.pentagonSubtilesPerTile==count,"Save/load failed.");
        Require(!System.IO.File.Exists(path+".tmp"),"Temporary save file was left behind.");
    }
    System.IO.File.WriteAllText(path,"{\"seed\":7}");
    Require(SphericalCivilization.WorldSettingsStore.TryLoad(path,out var partial) && partial.subtilesPerTile==37 && partial.seed==7,"Partial defaults failed.");
    System.IO.File.WriteAllText(path,"{\"subtilesPerTile\":54}");
    Require(SphericalCivilization.WorldSettingsStore.TryLoad(path,out var legacy) && legacy.hexagonSubtilesPerTile==54 && legacy.pentagonSubtilesPerTile==54,"Legacy count migration failed.");
    SphericalCivilization.WorldSettingsStore.Save(path,new SphericalCivilization.WorldSettings{subtilesPerTile=64,hexagonSubtilesPerTile=64,pentagonSubtilesPerTile=19,seed=7});
    Require(SphericalCivilization.WorldSettingsStore.TryLoad(path,out var mixed) && mixed.hexagonSubtilesPerTile==64 && mixed.pentagonSubtilesPerTile==19 && mixed.seed==7,"Independent counts were lost.");
    System.IO.File.WriteAllText(path,"{\"subtilesPerTile\":10000}");
    Require(SphericalCivilization.WorldSettingsStore.TryLoad(path,out var limited) && limited.subtilesPerTile==128,"Density limits failed.");
    System.IO.File.WriteAllText(path,"broken");
    Require(!SphericalCivilization.WorldSettingsStore.TryLoad(path,out var broken),"Invalid settings were accepted.");
    return new{result="PASS",savedUserPreferencesChanged=false};
}
finally
{
    if(System.IO.File.Exists(path))System.IO.File.Delete(path);
    if(System.IO.File.Exists(path+".tmp"))System.IO.File.Delete(path+".tmp");
    if(System.IO.Directory.Exists(directory))System.IO.Directory.Delete(directory);
}

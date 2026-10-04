pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "mirror"

// One Android module. It compiles src/mobile (integration, owned by claude) together with
// src/ui (screens and view model, owned by ag-a) so the UI folder stays untouched.
include(":app")
project(":app").projectDir = file("src/mobile")
